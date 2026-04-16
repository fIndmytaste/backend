# helpers/test_views.py
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.views import View
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .backblaze import BackblazeB2Helper, upload_to_backblaze, delete_from_backblaze

logger = logging.getLogger(__name__)


class BackblazeTestUploadView(APIView):
    """
    Test view for Backblaze B2 file upload functionality
    """
    parser_classes = (MultiPartParser, FormParser)
    
    @swagger_auto_schema(
        operation_description="Test Backblaze B2 file upload",
        manual_parameters=[
            openapi.Parameter(
                'file',
                openapi.IN_FORM,
                description="File to upload",
                type=openapi.TYPE_FILE,
                required=True
            ),
            openapi.Parameter(
                'folder',
                openapi.IN_FORM,
                description="Optional folder path",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'test_type',
                openapi.IN_FORM,
                description="Type of test: 'simple', 'with_folder', 'custom_name'",
                type=openapi.TYPE_STRING,
                required=False,
                default='simple'
            )
        ],
        responses={
            200: openapi.Response(
                description="Upload successful",
                examples={
                    "application/json": {
                        "success": True,
                        "message": "File uploaded successfully",
                        "file_info": {
                            "file_id": "4_z123456789abcdef_f123456789abcdef_d20231201_m123456_c001_v0001234_t0000",
                            "file_name": "test_file.jpg",
                            "download_url": "https://f000.backblazeb2.com/file/bucket/test_file.jpg",
                            "content_length": 12345,
                            "content_type": "image/jpeg"
                        }
                    }
                }
            ),
            400: openapi.Response(description="Bad request - no file provided"),
            500: openapi.Response(description="Upload failed")
        }
    )
    def post(self, request):
        """Upload a file to Backblaze B2 for testing"""
        try:
            # Check if file is provided
            if 'file' not in request.FILES:
                return Response({
                    'success': False,
                    'error': 'No file provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            uploaded_file = request.FILES['file']
            folder = request.data.get('folder', 'test_uploads')
            test_type = request.data.get('test_type', 'simple')
            
            # Prepare file name based on test type
            if test_type == 'custom_name':
                file_name = f"test_{uploaded_file.name}"
            elif test_type == 'with_timestamp':
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                file_name = f"{timestamp}_{uploaded_file.name}"
            else:
                file_name = uploaded_file.name
            
            # Upload to Backblaze
            result = upload_to_backblaze(
                file=uploaded_file,
                file_name=file_name,
                folder=folder,
                content_type=uploaded_file.content_type
            )
            
            return Response({
                'success': True,
                'message': 'File uploaded successfully to Backblaze B2',
                'test_type': test_type,
                'file_info': {
                    'file_id': result['fileId'],
                    'file_name': result['fileName'],
                    'download_url': result['downloadUrl'],
                    'content_length': result['contentLength'],
                    'content_type': result['contentType'],
                    'upload_timestamp': result['uploadTimestamp']
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Backblaze upload test failed: {e}")
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Upload failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BackblazeTestDeleteView(APIView):
    """
    Test view for Backblaze B2 file deletion functionality
    """
    
    @swagger_auto_schema(
        operation_description="Test Backblaze B2 file deletion",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'file_name': openapi.Schema(type=openapi.TYPE_STRING, description='Name of file to delete'),
                'file_id': openapi.Schema(type=openapi.TYPE_STRING, description='Backblaze file ID'),
            },
            required=['file_name', 'file_id']
        ),
        responses={
            200: openapi.Response(description="Deletion successful"),
            400: openapi.Response(description="Bad request"),
            500: openapi.Response(description="Deletion failed")
        }
    )
    def post(self, request):
        """Delete a file from Backblaze B2 for testing"""
        try:
            file_name = request.data.get('file_name')
            file_id = request.data.get('file_id')
            
            if not file_name or not file_id:
                return Response({
                    'success': False,
                    'error': 'file_name and file_id are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Delete from Backblaze
            success = delete_from_backblaze(file_name, file_id)
            
            if success:
                return Response({
                    'success': True,
                    'message': f'File {file_name} deleted successfully from Backblaze B2'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': 'Deletion returned False'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Backblaze deletion test failed: {e}")
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Deletion failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BackblazeTestListView(APIView):
    """
    Test view for listing files in Backblaze B2
    """
    
    @swagger_auto_schema(
        operation_description="Test Backblaze B2 file listing",
        manual_parameters=[
            openapi.Parameter(
                'folder',
                openapi.IN_QUERY,
                description="Optional folder to filter by",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'max_files',
                openapi.IN_QUERY,
                description="Maximum number of files to return",
                type=openapi.TYPE_INTEGER,
                required=False,
                default=10
            )
        ],
        responses={
            200: openapi.Response(description="Files listed successfully"),
            500: openapi.Response(description="Listing failed")
        }
    )
    def get(self, request):
        """List files in Backblaze B2 for testing"""
        try:
            folder = request.query_params.get('folder')
            max_files = int(request.query_params.get('max_files', 10))
            
            # Initialize helper
            helper = BackblazeB2Helper()
            
            # List files
            result = helper.list_files(folder=folder, max_files=max_files)
            
            return Response({
                'success': True,
                'message': 'Files listed successfully',
                'folder': folder,
                'file_count': len(result.get('files', [])),
                'files': result.get('files', [])
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Backblaze list test failed: {e}")
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Listing failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BackblazeTestInfoView(APIView):
    """
    Test view for getting file info from Backblaze B2
    """
    
    @swagger_auto_schema(
        operation_description="Test Backblaze B2 file info retrieval",
        manual_parameters=[
            openapi.Parameter(
                'file_id',
                openapi.IN_QUERY,
                description="Backblaze file ID",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: openapi.Response(description="File info retrieved successfully"),
            400: openapi.Response(description="Bad request"),
            500: openapi.Response(description="Info retrieval failed")
        }
    )
    def get(self, request):
        """Get file info from Backblaze B2 for testing"""
        try:
            file_id = request.query_params.get('file_id')
            
            if not file_id:
                return Response({
                    'success': False,
                    'error': 'file_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Initialize helper
            helper = BackblazeB2Helper()
            
            # Get file info
            file_info = helper.get_file_info(file_id)
            
            return Response({
                'success': True,
                'message': 'File info retrieved successfully',
                'file_info': file_info
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Backblaze file info test failed: {e}")
            return Response({
                'success': False,
                'error': str(e),
                'message': 'File info retrieval failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# HTML template view for easy testing
@method_decorator(csrf_exempt, name='dispatch')
class BackblazeTestPageView(View):
    """
    HTML page for testing Backblaze upload functionality
    """
    
    def get(self, request):
        """Render the test page"""
        return render(request, 'backblaze_test.html')


# Function-based view for simple testing
@csrf_exempt
@require_http_methods(["POST"])
def simple_backblaze_test(request):
    """Simple function-based view for quick Backblaze testing"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'No file provided'}, status=400)
        
        uploaded_file = request.FILES['file']
        
        # Upload to test folder
        result = upload_to_backblaze(
            file=uploaded_file,
            file_name=f"simple_test_{uploaded_file.name}",
            folder="simple_tests"
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Simple upload test successful',
            'download_url': result['downloadUrl'],
            'file_id': result['fileId']
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)