# helpers/management/commands/test_backblaze.py
import os
import tempfile
from django.core.management.base import BaseCommand, CommandError
from django.core.files.uploadedfile import SimpleUploadedFile
from helpers.backblaze import BackblazeB2Helper, upload_to_backblaze, delete_from_backblaze


class Command(BaseCommand):
    help = 'Test Backblaze B2 upload functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file-path',
            type=str,
            help='Path to file to upload (optional, will create test file if not provided)',
        )
        parser.add_argument(
            '--test-type',
            type=str,
            choices=['upload', 'list', 'delete', 'full'],
            default='full',
            help='Type of test to run',
        )
        parser.add_argument(
            '--folder',
            type=str,
            default='command_tests',
            help='Folder to upload to',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Delete uploaded test files after testing',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting Backblaze B2 Test...')
        )
        
        test_type = options['test_type']
        folder = options['folder']
        file_path = options['file_path']
        cleanup = options['cleanup']
        
        try:
            # Initialize helper
            helper = BackblazeB2Helper()
            self.stdout.write('✅ Backblaze helper initialized successfully')
            
            if test_type in ['upload', 'full']:
                self.test_upload(helper, file_path, folder, cleanup)
            
            if test_type in ['list', 'full']:
                self.test_list(helper, folder)
            
            if test_type in ['delete', 'full'] and not cleanup:
                self.stdout.write(
                    self.style.WARNING('⚠️  Delete test skipped. Use --cleanup to test deletion.')
                )
            
            self.stdout.write(
                self.style.SUCCESS('🎉 All Backblaze tests completed successfully!')
            )
            
        except Exception as e:
            raise CommandError(f'❌ Backblaze test failed: {e}')

    def test_upload(self, helper, file_path, folder, cleanup):
        """Test file upload functionality"""
        self.stdout.write('\n📤 Testing file upload...')
        
        # Create or use provided file
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                file_content = f.read()
            file_name = os.path.basename(file_path)
            self.stdout.write(f'📁 Using provided file: {file_path}')
        else:
            # Create a test file
            test_content = f"""
# Backblaze Test File
This is a test file created by the Django management command.
Timestamp: {helper._get_current_timestamp()}
Folder: {folder}
Test Type: Upload Test

This file can be safely deleted.
""".strip()
            file_content = test_content.encode('utf-8')
            file_name = f'test_file_{helper._get_current_timestamp()}.txt'
            self.stdout.write(f'📝 Created test file: {file_name}')
        
        # Create Django file object
        django_file = SimpleUploadedFile(
            file_name,
            file_content,
            content_type='text/plain'
        )
        
        try:
            # Upload file
            result = upload_to_backblaze(
                file=django_file,
                file_name=file_name,
                folder=folder
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Upload successful!')
            )
            self.stdout.write(f'   📄 File Name: {result["fileName"]}')
            self.stdout.write(f'   🆔 File ID: {result["fileId"]}')
            self.stdout.write(f'   🔗 Download URL: {result["downloadUrl"]}')
            self.stdout.write(f'   📏 Size: {result["contentLength"]} bytes')
            
            # Store for cleanup
            if cleanup:
                self.cleanup_file(result["fileName"], result["fileId"])
                
            return result
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Upload failed: {e}')
            )
            raise

    def test_list(self, helper, folder):
        """Test file listing functionality"""
        self.stdout.write('\n📋 Testing file listing...')
        
        try:
            # List all files
            all_files = helper.list_files(max_files=5)
            self.stdout.write(f'📊 Total files in bucket: {len(all_files.get("files", []))}')
            
            # List files in specific folder
            if folder:
                folder_files = helper.list_files(folder=folder, max_files=10)
                self.stdout.write(f'📁 Files in "{folder}" folder: {len(folder_files.get("files", []))}')
                
                # Display some file details
                for i, file_info in enumerate(folder_files.get("files", [])[:3]):
                    self.stdout.write(f'   {i+1}. {file_info["fileName"]} ({file_info["size"]} bytes)')
            
            self.stdout.write(
                self.style.SUCCESS('✅ File listing successful!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ File listing failed: {e}')
            )
            raise

    def cleanup_file(self, file_name, file_id):
        """Clean up uploaded test file"""
        self.stdout.write(f'\n🧹 Cleaning up test file: {file_name}')
        
        try:
            success = delete_from_backblaze(file_name, file_id)
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ File deleted successfully!')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  File deletion returned False')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ File deletion failed: {e}')
            )

    def test_connection(self):
        """Test basic connection to Backblaze"""
        self.stdout.write('\n🔌 Testing Backblaze connection...')
        
        try:
            helper = BackblazeB2Helper()
            # Try to get bucket info
            bucket_info = helper.list_files(max_files=1)
            self.stdout.write(
                self.style.SUCCESS('✅ Connection successful!')
            )
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Connection failed: {e}')
            )
            return False