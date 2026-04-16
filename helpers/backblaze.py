# helpers/backblaze.py
import os
import hashlib
import logging
from typing import Optional, Dict, Any, Union, BinaryIO
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
import requests
import json

logger = logging.getLogger(__name__)


class BackblazeB2Helper:
    """
    Helper class for uploading files to Backblaze B2 cloud storage
    """
    
    def __init__(self, 
                 application_key_id: Optional[str] = None,
                 application_key: Optional[str] = None,
                 bucket_id: Optional[str] = None,
                 bucket_name: Optional[str] = None):
        """
        Initialize Backblaze B2 helper
        
        Args:
            application_key_id: B2 application key ID (defaults to settings)
            application_key: B2 application key (defaults to settings)
            bucket_id: B2 bucket ID (defaults to settings)
            bucket_name: B2 bucket name (defaults to settings)
        """
        self.application_key_id = application_key_id or getattr(settings, 'BACKBLAZE_APPLICATION_KEY_ID', None)
        self.application_key = application_key or getattr(settings, 'BACKBLAZE_APPLICATION_KEY', None)
        self.bucket_id = bucket_id or getattr(settings, 'BACKBLAZE_BUCKET_ID', None)
        self.bucket_name = bucket_name or getattr(settings, 'BACKBLAZE_BUCKET_NAME', None)
        
        # Validate required credentials
        missing_credentials = []
        if not self.application_key_id:
            missing_credentials.append('BACKBLAZE_APPLICATION_KEY_ID')
        if not self.application_key:
            missing_credentials.append('BACKBLAZE_APPLICATION_KEY')
        if not self.bucket_id:
            missing_credentials.append('BACKBLAZE_BUCKET_ID')
        if not self.bucket_name:
            missing_credentials.append('BACKBLAZE_BUCKET_NAME')
        
        if missing_credentials:
            raise ValueError(
                f"Missing required Backblaze B2 credentials: {', '.join(missing_credentials)}. "
                f"Please set these environment variables in your .env file or Django settings."
            )
        
        self.api_url = None
        self.auth_token = None
        self.download_url = None
        self._authorize()
    
    def _authorize(self) -> None:
        """Authorize with Backblaze B2 API"""
        try:
            auth_url = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
            
            response = requests.get(
                auth_url,
                auth=(self.application_key_id, self.application_key),
                timeout=30
            )
            response.raise_for_status()
            
            auth_data = response.json()
            self.api_url = auth_data['apiUrl']
            self.auth_token = auth_data['authorizationToken']
            self.download_url = auth_data['downloadUrl']
            
            logger.info("Successfully authorized with Backblaze B2")
            
        except requests.RequestException as e:
            logger.error(f"Failed to authorize with Backblaze B2: {e}")
            raise Exception(f"Backblaze B2 authorization failed: {e}")
    
    def _get_upload_url(self) -> Dict[str, str]:
        """Get upload URL and authorization token for the bucket"""
        try:
            url = f"{self.api_url}/b2api/v2/b2_get_upload_url"
            headers = {'Authorization': self.auth_token}
            data = {'bucketId': self.bucket_id}
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to get upload URL: {e}")
            raise Exception(f"Failed to get upload URL: {e}")
    
    def _calculate_sha1(self, file_data: bytes) -> str:
        """Calculate SHA1 hash of file data"""
        return hashlib.sha1(file_data).hexdigest()
    
    def upload_file(self, 
                   file: Union[InMemoryUploadedFile, TemporaryUploadedFile, BinaryIO, bytes],
                   file_name: str,
                   folder: Optional[str] = None,
                   content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload a file to Backblaze B2
        
        Args:
            file: File to upload (Django uploaded file, file object, or bytes)
            file_name: Name for the file in B2
            folder: Optional folder path (will be prepended to file_name)
            content_type: Optional content type (auto-detected if not provided)
            
        Returns:
            Dict containing upload result with file info
        """
        try:
            # Prepare file data
            if isinstance(file, (InMemoryUploadedFile, TemporaryUploadedFile)):
                file_data = file.read()
                if not content_type:
                    content_type = file.content_type or 'application/octet-stream'
            elif isinstance(file, bytes):
                file_data = file
            else:
                file_data = file.read()
            
            if not content_type:
                content_type = 'application/octet-stream'
            
            # Prepare file name with folder
            if folder:
                file_name = f"{folder.strip('/')}/{file_name}"
            
            # Get upload URL
            upload_info = self._get_upload_url()
            upload_url = upload_info['uploadUrl']
            upload_auth_token = upload_info['authorizationToken']
            
            # Calculate SHA1
            sha1_hash = self._calculate_sha1(file_data)
            
            # Prepare headers
            headers = {
                'Authorization': upload_auth_token,
                'X-Bz-File-Name': file_name,
                'Content-Type': content_type,
                'X-Bz-Content-Sha1': sha1_hash,
                'X-Bz-Info-src_last_modified_millis': str(int(os.path.getmtime(__file__) * 1000))
            }
            
            # Upload file
            response = requests.post(
                upload_url,
                headers=headers,
                data=file_data,
                timeout=300  # 5 minutes timeout for large files
            )
            response.raise_for_status()
            
            upload_result = response.json()
            
            # Add download URL to result
            download_url = f"{self.download_url}/file/{self.bucket_name}/{file_name}"
            upload_result['downloadUrl'] = download_url
            
            logger.info(f"Successfully uploaded file: {file_name}")
            return upload_result
            
        except requests.RequestException as e:
            logger.error(f"Failed to upload file {file_name}: {e}")
            raise Exception(f"File upload failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error uploading file {file_name}: {e}")
            raise
    
    def delete_file(self, file_name: str, file_id: str) -> bool:
        """
        Delete a file from Backblaze B2
        
        Args:
            file_name: Name of the file to delete
            file_id: B2 file ID
            
        Returns:
            True if successful
        """
        try:
            url = f"{self.api_url}/b2api/v2/b2_delete_file_version"
            headers = {'Authorization': self.auth_token}
            data = {
                'fileId': file_id,
                'fileName': file_name
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            logger.info(f"Successfully deleted file: {file_name}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to delete file {file_name}: {e}")
            raise Exception(f"File deletion failed: {e}")
    
    def delete_file_by_url(self, download_url: str, file_id: str) -> bool:
        """
        Delete a file using its download URL
        
        Args:
            download_url: The download URL of the file
            file_id: B2 file ID
            
        Returns:
            True if successful
        """
        try:
            # Extract file name from URL
            file_name = download_url.split('/')[-1]
            return self.delete_file(file_name, file_id)
            
        except Exception as e:
            logger.error(f"Failed to delete file by URL {download_url}: {e}")
            raise Exception(f"File deletion by URL failed: {e}")
    
    def delete_multiple_files(self, files: list) -> Dict[str, Any]:
        """
        Delete multiple files from Backblaze B2
        
        Args:
            files: List of dictionaries with 'file_name' and 'file_id' keys
                   Example: [{'file_name': 'file1.jpg', 'file_id': 'id1'}, ...]
            
        Returns:
            Dict with success/failure counts and details
        """
        results = {
            'successful': [],
            'failed': [],
            'success_count': 0,
            'failure_count': 0
        }
        
        for file_info in files:
            try:
                file_name = file_info.get('file_name')
                file_id = file_info.get('file_id')
                
                if not file_name or not file_id:
                    results['failed'].append({
                        'file_info': file_info,
                        'error': 'Missing file_name or file_id'
                    })
                    results['failure_count'] += 1
                    continue
                
                success = self.delete_file(file_name, file_id)
                if success:
                    results['successful'].append(file_info)
                    results['success_count'] += 1
                else:
                    results['failed'].append({
                        'file_info': file_info,
                        'error': 'Deletion returned False'
                    })
                    results['failure_count'] += 1
                    
            except Exception as e:
                results['failed'].append({
                    'file_info': file_info,
                    'error': str(e)
                })
                results['failure_count'] += 1
        
        logger.info(f"Bulk deletion completed: {results['success_count']} successful, {results['failure_count']} failed")
        return results
    
    def delete_files_by_folder(self, folder: str, max_files: int = 100) -> Dict[str, Any]:
        """
        Delete all files in a specific folder
        
        Args:
            folder: Folder path to delete files from
            max_files: Maximum number of files to delete (safety limit)
            
        Returns:
            Dict with deletion results
        """
        try:
            # List files in the folder
            files_response = self.list_files(folder=folder, max_files=max_files)
            files = files_response.get('files', [])
            
            if not files:
                logger.info(f"No files found in folder: {folder}")
                return {
                    'successful': [],
                    'failed': [],
                    'success_count': 0,
                    'failure_count': 0,
                    'message': f'No files found in folder: {folder}'
                }
            
            # Prepare file list for bulk deletion
            files_to_delete = []
            for file_info in files:
                files_to_delete.append({
                    'file_name': file_info['fileName'],
                    'file_id': file_info['fileId']
                })
            
            # Delete files
            results = self.delete_multiple_files(files_to_delete)
            results['folder'] = folder
            
            logger.info(f"Deleted {results['success_count']} files from folder: {folder}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to delete files from folder {folder}: {e}")
            raise Exception(f"Folder deletion failed: {e}")
    
    def delete_files_by_pattern(self, pattern: str, max_files: int = 100) -> Dict[str, Any]:
        """
        Delete files matching a specific pattern
        
        Args:
            pattern: Pattern to match file names (simple string matching)
            max_files: Maximum number of files to check and delete
            
        Returns:
            Dict with deletion results
        """
        try:
            # List all files
            files_response = self.list_files(max_files=max_files)
            all_files = files_response.get('files', [])
            
            # Filter files by pattern
            matching_files = []
            for file_info in all_files:
                if pattern in file_info['fileName']:
                    matching_files.append({
                        'file_name': file_info['fileName'],
                        'file_id': file_info['fileId']
                    })
            
            if not matching_files:
                logger.info(f"No files found matching pattern: {pattern}")
                return {
                    'successful': [],
                    'failed': [],
                    'success_count': 0,
                    'failure_count': 0,
                    'message': f'No files found matching pattern: {pattern}'
                }
            
            # Delete matching files
            results = self.delete_multiple_files(matching_files)
            results['pattern'] = pattern
            
            logger.info(f"Deleted {results['success_count']} files matching pattern: {pattern}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to delete files by pattern {pattern}: {e}")
            raise Exception(f"Pattern deletion failed: {e}")
    
    def get_file_info(self, file_id: str) -> Dict[str, Any]:
        """
        Get information about a file
        
        Args:
            file_id: B2 file ID
            
        Returns:
            Dict containing file information
        """
        try:
            url = f"{self.api_url}/b2api/v2/b2_get_file_info"
            headers = {'Authorization': self.auth_token}
            data = {'fileId': file_id}
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to get file info for {file_id}: {e}")
            raise Exception(f"Failed to get file info: {e}")
    
    def list_files(self, folder: Optional[str] = None, max_files: int = 100) -> Dict[str, Any]:
        """
        List files in the bucket
        
        Args:
            folder: Optional folder to filter by
            max_files: Maximum number of files to return
            
        Returns:
            Dict containing list of files
        """
        try:
            url = f"{self.api_url}/b2api/v2/b2_list_file_names"
            headers = {'Authorization': self.auth_token}
            data = {
                'bucketId': self.bucket_id,
                'maxFileCount': max_files
            }
            
            if folder:
                data['startFileName'] = folder.strip('/') + '/'
                data['prefix'] = folder.strip('/') + '/'
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to list files: {e}")
            raise Exception(f"Failed to list files: {e}")


# Convenience functions for easy usage
def upload_to_backblaze(file, file_name: str, folder: Optional[str] = None, 
                       content_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to upload a file to Backblaze B2
    
    Args:
        file: File to upload
        file_name: Name for the file in B2
        folder: Optional folder path
        content_type: Optional content type
        
    Returns:
        Dict containing upload result
    """
    helper = BackblazeB2Helper()
    return helper.upload_file(file, file_name, folder, content_type)


def delete_from_backblaze(file_name: str, file_id: str) -> bool:
    """
    Convenience function to delete a file from Backblaze B2
    
    Args:
        file_name: Name of the file to delete
        file_id: B2 file ID
        
    Returns:
        True if successful
    """
    helper = BackblazeB2Helper()
    return helper.delete_file(file_name, file_id)


def delete_by_url_from_backblaze(download_url: str, file_id: str) -> bool:
    """
    Convenience function to delete a file by its download URL
    
    Args:
        download_url: The download URL of the file
        file_id: B2 file ID
        
    Returns:
        True if successful
    """
    helper = BackblazeB2Helper()
    return helper.delete_file_by_url(download_url, file_id)


def delete_multiple_from_backblaze(files: list) -> Dict[str, Any]:
    """
    Convenience function to delete multiple files from Backblaze B2
    
    Args:
        files: List of dictionaries with 'file_name' and 'file_id' keys
        
    Returns:
        Dict with deletion results
    """
    helper = BackblazeB2Helper()
    return helper.delete_multiple_files(files)


def delete_folder_from_backblaze(folder: str, max_files: int = 100) -> Dict[str, Any]:
    """
    Convenience function to delete all files in a folder
    
    Args:
        folder: Folder path to delete files from
        max_files: Maximum number of files to delete
        
    Returns:
        Dict with deletion results
    """
    helper = BackblazeB2Helper()
    return helper.delete_files_by_folder(folder, max_files)


def delete_by_pattern_from_backblaze(pattern: str, max_files: int = 100) -> Dict[str, Any]:
    """
    Convenience function to delete files matching a pattern
    
    Args:
        pattern: Pattern to match file names
        max_files: Maximum number of files to check and delete
        
    Returns:
        Dict with deletion results
    """
    helper = BackblazeB2Helper()
    return helper.delete_files_by_pattern(pattern, max_files)