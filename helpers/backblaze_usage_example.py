# helpers/backblaze_usage_example.py
"""
Usage examples for the Backblaze B2 Helper class
"""

from django.core.files.uploadedfile import InMemoryUploadedFile
from helpers.backblaze import BackblazeB2Helper, upload_to_backblaze, delete_from_backblaze


# Example 1: Using the helper class directly
def upload_user_avatar(user, avatar_file):
    """Upload user avatar to Backblaze B2"""
    try:
        # Initialize the helper
        b2_helper = BackblazeB2Helper()
        
        # Upload file to avatars folder
        file_name = f"avatar_{user.id}_{avatar_file.name}"
        result = b2_helper.upload_file(
            file=avatar_file,
            file_name=file_name,
            folder="avatars",
            content_type=avatar_file.content_type
        )
        
        # Save the download URL to user model
        user.avatar_url = result['downloadUrl']
        user.avatar_file_id = result['fileId']  # Save for future deletion
        user.save()
        
        return result
        
    except Exception as e:
        print(f"Failed to upload avatar: {e}")
        return None


# Example 2: Using convenience functions
def upload_product_image(product, image_file):
    """Upload product image using convenience function"""
    try:
        file_name = f"product_{product.id}_{image_file.name}"
        result = upload_to_backblaze(
            file=image_file,
            file_name=file_name,
            folder="products",
            content_type=image_file.content_type
        )
        
        # Save to product model
        product.image_url = result['downloadUrl']
        product.image_file_id = result['fileId']
        product.save()
        
        return result
        
    except Exception as e:
        print(f"Failed to upload product image: {e}")
        return None


# Example 3: Django view for file upload
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

@csrf_exempt
@require_http_methods(["POST"])
def upload_file_view(request):
    """Django view to handle file uploads to Backblaze B2"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'No file provided'}, status=400)
        
        uploaded_file = request.FILES['file']
        folder = request.POST.get('folder', 'uploads')
        
        # Upload to Backblaze
        result = upload_to_backblaze(
            file=uploaded_file,
            file_name=uploaded_file.name,
            folder=folder
        )
        
        return JsonResponse({
            'success': True,
            'file_id': result['fileId'],
            'file_name': result['fileName'],
            'download_url': result['downloadUrl'],
            'size': result['contentLength']
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Example 4: Delete file
def delete_user_avatar(user):
    """Delete user avatar from Backblaze B2"""
    try:
        if user.avatar_file_id:
            success = delete_from_backblaze(
                file_name=user.avatar_url.split('/')[-1],  # Extract filename from URL
                file_id=user.avatar_file_id
            )
            
            if success:
                user.avatar_url = None
                user.avatar_file_id = None
                user.save()
                return True
                
    except Exception as e:
        print(f"Failed to delete avatar: {e}")
        return False


# Example 4b: Delete file by URL (easier method)
def delete_user_avatar_by_url(user):
    """Delete user avatar using download URL"""
    try:
        if user.avatar_url and user.avatar_file_id:
            success = delete_by_url_from_backblaze(
                download_url=user.avatar_url,
                file_id=user.avatar_file_id
            )
            
            if success:
                user.avatar_url = None
                user.avatar_file_id = None
                user.save()
                return True
                
    except Exception as e:
        print(f"Failed to delete avatar by URL: {e}")
        return False


# Example 4c: Delete multiple files
def delete_user_files(user_files):
    """Delete multiple user files at once"""
    try:
        # Prepare file list
        files_to_delete = []
        for user_file in user_files:
            if user_file.file_id and user_file.file_url:
                files_to_delete.append({
                    'file_name': user_file.file_url.split('/')[-1],
                    'file_id': user_file.file_id
                })
        
        # Delete multiple files
        results = delete_multiple_from_backblaze(files_to_delete)
        
        # Update database for successful deletions
        for successful_file in results['successful']:
            # Find and update the corresponding user file
            for user_file in user_files:
                if user_file.file_id == successful_file['file_id']:
                    user_file.file_url = None
                    user_file.file_id = None
                    user_file.save()
                    break
        
        return results
        
    except Exception as e:
        print(f"Failed to delete multiple files: {e}")
        return None


# Example 4d: Delete all files in a folder
def cleanup_temp_uploads():
    """Delete all temporary upload files"""
    try:
        results = delete_folder_from_backblaze(
            folder="temp_uploads",
            max_files=200
        )
        
        print(f"Cleanup completed: {results['success_count']} files deleted")
        if results['failure_count'] > 0:
            print(f"Failed to delete {results['failure_count']} files")
            
        return results
        
    except Exception as e:
        print(f"Failed to cleanup temp uploads: {e}")
        return None


# Example 4e: Delete files by pattern
def delete_old_thumbnails():
    """Delete old thumbnail files"""
    try:
        # Delete all files containing 'thumbnail_old' in the name
        results = delete_by_pattern_from_backblaze(
            pattern="thumbnail_old",
            max_files=100
        )
        
        print(f"Deleted {results['success_count']} old thumbnails")
        return results
        
    except Exception as e:
        print(f"Failed to delete old thumbnails: {e}")
        return None


# Example 5: Upload with custom configuration
def upload_with_custom_config():
    """Upload using custom Backblaze configuration"""
    try:
        # Use custom credentials (useful for multiple buckets)
        custom_helper = BackblazeB2Helper(
            application_key_id='custom_key_id',
            application_key='custom_key',
            bucket_id='custom_bucket_id',
            bucket_name='custom_bucket_name'
        )
        
        # Upload file
        with open('local_file.jpg', 'rb') as f:
            result = custom_helper.upload_file(
                file=f,
                file_name='uploaded_file.jpg',
                folder='custom_folder',
                content_type='image/jpeg'
            )
            
        return result
        
    except Exception as e:
        print(f"Upload failed: {e}")
        return None


# Example 6: List files in bucket
def list_bucket_files():
    """List files in the Backblaze B2 bucket"""
    try:
        b2_helper = BackblazeB2Helper()
        
        # List all files
        all_files = b2_helper.list_files(max_files=100)
        
        # List files in specific folder
        product_files = b2_helper.list_files(folder='products', max_files=50)
        
        return {
            'all_files': all_files,
            'product_files': product_files
        }
        
    except Exception as e:
        print(f"Failed to list files: {e}")
        return None


# Example 7: Get file information
def get_file_details(file_id):
    """Get detailed information about a file"""
    try:
        b2_helper = BackblazeB2Helper()
        file_info = b2_helper.get_file_info(file_id)
        
        return {
            'file_id': file_info['fileId'],
            'file_name': file_info['fileName'],
            'content_type': file_info['contentType'],
            'content_length': file_info['contentLength'],
            'upload_timestamp': file_info['uploadTimestamp']
        }
        
    except Exception as e:
        print(f"Failed to get file info: {e}")
        return None


# Example 8: Django model integration
from django.db import models

class Document(models.Model):
    """Example model with Backblaze B2 integration"""
    title = models.CharField(max_length=200)
    file_url = models.URLField(blank=True, null=True)
    file_id = models.CharField(max_length=100, blank=True, null=True)  # B2 file ID
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def upload_file(self, file):
        """Upload file to Backblaze B2"""
        try:
            file_name = f"document_{self.id}_{file.name}"
            result = upload_to_backblaze(
                file=file,
                file_name=file_name,
                folder="documents"
            )
            
            self.file_url = result['downloadUrl']
            self.file_id = result['fileId']
            self.save()
            
            return True
            
        except Exception as e:
            print(f"Failed to upload document: {e}")
            return False
    
    def delete_file(self):
        """Delete file from Backblaze B2"""
        try:
            if self.file_id and self.file_url:
                file_name = self.file_url.split('/')[-1]
                success = delete_from_backblaze(file_name, self.file_id)
                
                if success:
                    self.file_url = None
                    self.file_id = None
                    self.save()
                    
                return success
                
        except Exception as e:
            print(f"Failed to delete document: {e}")
            return False
    
    def delete_file_by_url(self):
        """Delete file using download URL (easier method)"""
        try:
            if self.file_id and self.file_url:
                success = delete_by_url_from_backblaze(self.file_url, self.file_id)
                
                if success:
                    self.file_url = None
                    self.file_id = None
                    self.save()
                    
                return success
                
        except Exception as e:
            print(f"Failed to delete document by URL: {e}")
            return False
    
    @classmethod
    def delete_multiple_documents(cls, document_ids):
        """Delete multiple documents at once"""
        try:
            documents = cls.objects.filter(id__in=document_ids, file_id__isnull=False)
            
            # Prepare file list
            files_to_delete = []
            for doc in documents:
                if doc.file_id and doc.file_url:
                    files_to_delete.append({
                        'file_name': doc.file_url.split('/')[-1],
                        'file_id': doc.file_id
                    })
            
            # Delete from Backblaze
            results = delete_multiple_from_backblaze(files_to_delete)
            
            # Update database for successful deletions
            for successful_file in results['successful']:
                documents.filter(file_id=successful_file['file_id']).update(
                    file_url=None,
                    file_id=None
                )
            
            return results
            
        except Exception as e:
            print(f"Failed to delete multiple documents: {e}")
            return None