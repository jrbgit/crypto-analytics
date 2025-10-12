"""
Data storage service with comprehensive change tracking and data management.
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from contextlib import contextmanager

from sqlalchemy.orm import Session
from loguru import logger

from database import (
    DatabaseManager, CryptoProject, ProjectLink, ProjectImage, 
    ProjectChange, LinkContentAnalysis, ProjectAnalysis, APIUsage
)


class ChangeTracker:
    """Handles change detection and tracking for project data."""
    
    @staticmethod
    def serialize_value(value: Any) -> str:
        """Serialize any value to a JSON string for storage."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        return json.dumps(value, default=str, sort_keys=True)
    
    @staticmethod
    def has_changed(old_value: Any, new_value: Any) -> bool:
        """Check if a value has actually changed."""
        if old_value is None and new_value is None:
            return False
        if old_value is None or new_value is None:
            return True
        
        # For numeric values, handle small floating point differences
        if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
            return abs(float(old_value) - float(new_value)) > 1e-10
            
        return old_value != new_value
    
    @staticmethod
    def create_change_record(project_id: int, field_name: str, old_value: Any, 
                           new_value: Any, data_source: str = 'livecoinwatch',
                           api_endpoint: str = None) -> ProjectChange:
        """Create a change record for tracking."""
        return ProjectChange(
            project_id=project_id,
            field_name=field_name,
            old_value=ChangeTracker.serialize_value(old_value),
            new_value=ChangeTracker.serialize_value(new_value),
            change_type='UPDATE',
            data_source=data_source,
            api_endpoint=api_endpoint
        )


class CryptoDataService:
    """Service for managing cryptocurrency project data with change tracking."""
    
    def __init__(self, database_manager: DatabaseManager):
        self.db_manager = database_manager
        self.change_tracker = ChangeTracker()
        
    @contextmanager
    def get_session(self):
        """Get a database session with proper cleanup."""
        session = self.db_manager.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def upsert_project(self, coin_data: Dict, data_source: str = 'livecoinwatch') -> CryptoProject:
        """Insert or update a crypto project with full change tracking."""
        
        with self.get_session() as session:
            # Find existing project
            existing_project = session.query(CryptoProject).filter_by(
                code=coin_data['code']
            ).first()
            
            changes = []
            
            if existing_project:
                project = existing_project
                logger.debug(f"Updating existing project: {project.name}")
                
                # Track changes for all relevant fields
                changes = self._track_project_changes(project, coin_data, data_source)
                
            else:
                # Create new project
                project = CryptoProject(code=coin_data['code'])
                session.add(project)
                logger.info(f"Creating new project: {coin_data.get('name', 'Unknown')}")
            
            # Update all project fields
            self._update_project_fields(project, coin_data)
            
            # Process related data
            self._process_project_links(session, project, coin_data.get('links', {}))
            self._process_project_images(session, project, coin_data)
            
            # Save all changes
            for change in changes:
                session.add(change)
            
            session.flush()  # Ensure project.id is available for changes
            
            # Update timestamps
            project.last_api_fetch = datetime.utcnow()
            project.updated_at = datetime.utcnow()
            
            logger.success(f"Processed project: {project.name} ({len(changes)} changes tracked)")
            
            return project
    
    def _track_project_changes(self, project: CryptoProject, new_data: Dict, 
                              data_source: str) -> List[ProjectChange]:
        """Track changes to all project fields."""
        
        changes = []
        
        # Basic info fields
        basic_fields = {
            'name': new_data.get('name'),
            'rank': new_data.get('rank'),
            'age': new_data.get('age'),
            'color': new_data.get('color')
        }
        
        for field_name, new_value in basic_fields.items():
            old_value = getattr(project, field_name)
            if self.change_tracker.has_changed(old_value, new_value):
                changes.append(self.change_tracker.create_change_record(
                    project.id, field_name, old_value, new_value, data_source
                ))
        
        # Supply fields
        supply_fields = {
            'circulating_supply': new_data.get('circulatingSupply'),
            'total_supply': new_data.get('totalSupply'),
            'max_supply': new_data.get('maxSupply')
        }
        
        for field_name, new_value in supply_fields.items():
            old_value = getattr(project, field_name)
            if self.change_tracker.has_changed(old_value, new_value):
                changes.append(self.change_tracker.create_change_record(
                    project.id, field_name, old_value, new_value, data_source
                ))
        
        # Market data fields
        market_fields = {
            'current_price': new_data.get('rate'),
            'market_cap': new_data.get('cap'),
            'volume_24h': new_data.get('volume'),
            'ath_usd': new_data.get('allTimeHighUSD')
        }
        
        for field_name, new_value in market_fields.items():
            old_value = getattr(project, field_name)
            if self.change_tracker.has_changed(old_value, new_value):
                changes.append(self.change_tracker.create_change_record(
                    project.id, field_name, old_value, new_value, data_source
                ))
        
        # Price delta fields
        delta_data = new_data.get('delta', {})
        delta_fields = {
            'price_change_1h': delta_data.get('hour'),
            'price_change_24h': delta_data.get('day'),
            'price_change_7d': delta_data.get('week'),
            'price_change_30d': delta_data.get('month'),
            'price_change_90d': delta_data.get('quarter'),
            'price_change_1y': delta_data.get('year')
        }
        
        for field_name, new_value in delta_fields.items():
            old_value = getattr(project, field_name)
            if self.change_tracker.has_changed(old_value, new_value):
                changes.append(self.change_tracker.create_change_record(
                    project.id, field_name, old_value, new_value, data_source
                ))
        
        # Exchange fields
        exchange_fields = {
            'exchanges_count': new_data.get('exchanges'),
            'markets_count': new_data.get('markets'),
            'pairs_count': new_data.get('pairs')
        }
        
        for field_name, new_value in exchange_fields.items():
            old_value = getattr(project, field_name)
            if self.change_tracker.has_changed(old_value, new_value):
                changes.append(self.change_tracker.create_change_record(
                    project.id, field_name, old_value, new_value, data_source
                ))
        
        # Categories (JSON field)
        new_categories = new_data.get('categories')
        old_categories = project.categories
        if self.change_tracker.has_changed(old_categories, new_categories):
            changes.append(self.change_tracker.create_change_record(
                project.id, 'categories', old_categories, new_categories, data_source
            ))
        
        return changes
    
    def _update_project_fields(self, project: CryptoProject, coin_data: Dict):
        """Update all project fields with new data."""
        
        # Basic info
        project.name = coin_data.get('name')
        project.rank = coin_data.get('rank')
        project.age = coin_data.get('age')
        project.color = coin_data.get('color')
        
        # Supply data
        project.circulating_supply = coin_data.get('circulatingSupply')
        project.total_supply = coin_data.get('totalSupply')
        project.max_supply = coin_data.get('maxSupply')
        
        # Market data
        project.current_price = coin_data.get('rate')
        project.market_cap = coin_data.get('cap')
        project.volume_24h = coin_data.get('volume')
        project.ath_usd = coin_data.get('allTimeHighUSD')
        
        # Price deltas
        delta = coin_data.get('delta', {})
        project.price_change_1h = delta.get('hour')
        project.price_change_24h = delta.get('day')
        project.price_change_7d = delta.get('week')
        project.price_change_30d = delta.get('month')
        project.price_change_90d = delta.get('quarter')
        project.price_change_1y = delta.get('year')
        
        # Exchange data
        project.exchanges_count = coin_data.get('exchanges')
        project.markets_count = coin_data.get('markets')
        project.pairs_count = coin_data.get('pairs')
        
        # Categories
        project.categories = coin_data.get('categories')
    
    def _process_project_links(self, session: Session, project: CryptoProject, links_data: Dict):
        """Process and update project links with change tracking."""
        
        for link_type, url in links_data.items():
            if not url:  # Skip null/empty URLs
                continue
                
            # Find existing link
            existing_link = session.query(ProjectLink).filter_by(
                project_id=project.id,
                link_type=link_type
            ).first()
            
            if existing_link:
                if existing_link.url != url:
                    # URL changed - track the change
                    change = self.change_tracker.create_change_record(
                        project.id, f'link_{link_type}', existing_link.url, url
                    )
                    session.add(change)
                    
                    # Update the link and mark for re-analysis
                    existing_link.url = url
                    existing_link.needs_analysis = True
                    existing_link.updated_at = datetime.utcnow()
                    
                    logger.info(f"Updated {link_type} link for {project.name}")
            else:
                # New link
                new_link = ProjectLink(
                    project_id=project.id,
                    link_type=link_type,
                    url=url,
                    needs_analysis=True
                )
                session.add(new_link)
                
                # Track as a new addition
                change = self.change_tracker.create_change_record(
                    project.id, f'link_{link_type}', None, url
                )
                change.change_type = 'INSERT'
                session.add(change)
                
                logger.info(f"Added new {link_type} link for {project.name}")
    
    def _process_project_images(self, session: Session, project: CryptoProject, coin_data: Dict):
        """Process and update project images."""
        
        image_fields = ['png32', 'png64', 'webp32', 'webp64']
        
        for image_type in image_fields:
            url = coin_data.get(image_type)
            if not url:
                continue
                
            existing_image = session.query(ProjectImage).filter_by(
                project_id=project.id,
                image_type=image_type
            ).first()
            
            if existing_image:
                if existing_image.url != url:
                    existing_image.url = url
                    logger.debug(f"Updated {image_type} image for {project.name}")
            else:
                new_image = ProjectImage(
                    project_id=project.id,
                    image_type=image_type,
                    url=url
                )
                session.add(new_image)
                logger.debug(f"Added {image_type} image for {project.name}")
    
    def get_project_changes(self, project_id: int, field_name: str = None, 
                          limit: int = 100) -> List[ProjectChange]:
        """Get change history for a project."""
        
        with self.get_session() as session:
            query = session.query(ProjectChange).filter_by(project_id=project_id)
            
            if field_name:
                query = query.filter_by(field_name=field_name)
            
            return query.order_by(ProjectChange.created_at.desc()).limit(limit).all()
    
    def get_recent_changes(self, hours: int = 24, limit: int = 100) -> List[ProjectChange]:
        """Get recent changes across all projects."""
        
        with self.get_session() as session:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            return session.query(ProjectChange).filter(
                ProjectChange.created_at >= cutoff_time
            ).order_by(ProjectChange.created_at.desc()).limit(limit).all()
    
    def get_projects_needing_link_analysis(self, limit: int = 50) -> List[Tuple[CryptoProject, List[ProjectLink]]]:
        """Get projects with links that need LLM analysis."""
        
        with self.get_session() as session:
            # Get projects that have links needing analysis
            projects_with_pending_links = session.query(CryptoProject).join(
                ProjectLink
            ).filter(
                ProjectLink.needs_analysis == True
            ).distinct().limit(limit).all()
            
            result = []
            for project in projects_with_pending_links:
                pending_links = session.query(ProjectLink).filter_by(
                    project_id=project.id,
                    needs_analysis=True
                ).all()
                result.append((project, pending_links))
            
            return result
    
    def mark_link_analyzed(self, link_id: int, success: bool = True):
        """Mark a link as analyzed."""
        
        with self.get_session() as session:
            link = session.query(ProjectLink).get(link_id)
            if link:
                link.needs_analysis = False
                link.last_scraped = datetime.utcnow()
                link.scrape_success = success
                link.updated_at = datetime.utcnow()
    
    def get_project_stats(self) -> Dict[str, int]:
        """Get general statistics about the data."""
        
        with self.get_session() as session:
            total_projects = session.query(CryptoProject).count()
            total_links = session.query(ProjectLink).count()
            pending_analysis = session.query(ProjectLink).filter_by(needs_analysis=True).count()
            total_changes = session.query(ProjectChange).count()
            
            # Recent activity (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_changes = session.query(ProjectChange).filter(
                ProjectChange.created_at >= recent_cutoff
            ).count()
            
            return {
                'total_projects': total_projects,
                'total_links': total_links,
                'pending_link_analysis': pending_analysis,
                'total_changes_tracked': total_changes,
                'recent_changes_24h': recent_changes
            }
    
    def cleanup_old_changes(self, days_to_keep: int = 90) -> int:
        """Clean up old change records to prevent database bloat."""
        
        with self.get_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            deleted_count = session.query(ProjectChange).filter(
                ProjectChange.created_at < cutoff_date
            ).delete()
            
            logger.info(f"Cleaned up {deleted_count} old change records")
            return deleted_count
