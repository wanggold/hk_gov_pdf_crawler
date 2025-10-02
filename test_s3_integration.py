#!/usr/bin/env python3
"""
S3 Integration Tests

This module contains tests for S3 upload functionality using mocked AWS services
to test cloud storage integration without requiring actual AWS credentials.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, NoCredentialsError
import boto3

# Import modules to test
from config import StorageConfig
from downloader import FileDownloader
from models import DownloadResult


class TestS3Configuration:
    """Test S3 configuration and initialization"""
    
    def test_s3_disabled_configuration(self):
        """Test configuration with S3 disabled"""
        storage_config = StorageConfig(
            local_path='./downloads',
            s3_enabled=False,
            s3_bucket=None,
            s3_prefix=None
        )
        
        downloader = FileDownloader(storage_config)
        
        # S3 client should not be initialized
        assert downloader.s3_client is None
        assert storage_config.s3_enabled is False
    
    @patch('downloader.boto3.client')
    def test_s3_enabled_configuration(self, mock_boto3_client):
        """Test configuration with S3 enabled"""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        
        storage_config = StorageConfig(
            local_path='./downloads',
            s3_enabled=True,
            s3_bucket='test-bucket',
            s3_prefix='hk-pdfs/'
        )
        
        downloader = FileDownloader(storage_config)
        
        # S3 client should be initialized
        mock_boto3_client.assert_called_once_with('s3')
        assert downloader.s3_client is not None
    
    @patch('downloader.boto3.client')
    def test_s3_initialization_with_credentials_error(self, mock_boto3_client):
        """Test S3 initialization with credentials error"""
        mock_boto3_client.side_effect = NoCredentialsError()
        
        storage_config = StorageConfig(
            local_path='./downloads',
            s3_enabled=True,
            s3_bucket='test-bucket'
        )
        
        # Should handle credentials error gracefully
        downloader = FileDownloader(storage_config)
        
        # S3 client should be None due to error
        assert downloader.s3_client is None
    
    @patch('downloader.boto3.client')
    def test_s3_bucket_validation(self, mock_boto3_client):
        """Test S3 bucket validation during initialization"""
        mock_s3_client = Mock()
        mock_s3_client.head_bucket.return_value = {}  # Successful validation
        mock_boto3_client.return_value = mock_s3_client
        
        storage_config = StorageConfig(
            local_path='./downloads',
            s3_enabled=True,
            s3_bucket='valid-bucket'
        )
        
        downloader = FileDownloader(storage_config)
        
        # Should validate bucket exists
        mock_s3_client.head_bucket.assert_called_once_with(Bucket='valid-bucket')
        assert downloader.s3_client is not None
    
    @patch('downloader.boto3.client')
    def test_s3_bucket_validation_failure(self, mock_boto3_client):
        """Test S3 bucket validation failure"""
        mock_s3_client = Mock()
        mock_s3_client.head_bucket.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchBucket'}}, 'HeadBucket'
        )
        mock_boto3_client.return_value = mock_s3_client
        
        storage_config = StorageConfig(
            local_path='./downloads',
            s3_enabled=True,
            s3_bucket='nonexistent-bucket'
        )
        
        # Should handle bucket validation failure
        downloader = FileDownloader(storage_config)
        
        # S3 client should be None due to validation failure
        assert downloader.s3_client is None


class TestS3Upload:
    """Test S3 upload functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_config = StorageConfig(
            local_path=self.temp_dir,
            organize_by_department=True,
            s3_enabled=True,
            s3_bucket='test-bucket',
            s3_prefix='hk-government-pdfs/'
        )
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('downloader.boto3.client')
    def test_successful_s3_upload(self, mock_boto3_client):
        """Test successful S3 upload"""
        mock_s3_client = Mock()
        mock_s3_client.put_object.return_value = {}
        mock_boto3_client.return_value = mock_s3_client
        
        downloader = FileDownloader(self.storage_config)
        
        test_content = b'%PDF-1.4\nTest PDF content\n%%EOF'
        s3_key = 'hk-government-pdfs/test-dept/test-document.pdf'
        
        result = downloader.upload_to_s3(test_content, s3_key)
        
        assert result is True
        mock_s3_client.put_object.assert_called_once_with(
            Bucket='test-bucket',
            Key=s3_key,
            Body=test_content,
            ContentType='application/pdf',
            Metadata={
                'source': 'hk-pdf-crawler',
                'upload_time': mock_s3_client.put_object.call_args[1]['Metadata']['upload_time']
            }
        )
    
    @patch('downloader.boto3.client')
    def test_s3_upload_client_error(self, mock_boto3_client):
        """Test S3 upload with client error"""
        mock_s3_client = Mock()
        mock_s3_client.put_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'PutObject'
        )
        mock_boto3_client.return_value = mock_s3_client
        
        downloader = FileDownloader(self.storage_config)
        
        test_content = b'%PDF-1.4\nTest PDF content\n%%EOF'
        s3_key = 'test-key.pdf'
        
        result = downloader.upload_to_s3(test_content, s3_key)
        
        assert result is False
    
    @patch('downloader.boto3.client')
    def test_s3_upload_retry_mechanism(self, mock_boto3_client):
        """Test S3 upload retry mechanism"""
        mock_s3_client = Mock()
        
        # First two attempts fail, third succeeds
        mock_s3_client.put_object.side_effect = [
            ClientError({'Error': {'Code': 'ServiceUnavailable'}}, 'PutObject'),
            ClientError({'Error': {'Code': 'ServiceUnavailable'}}, 'PutObject'),
            {}  # Success
        ]
        mock_boto3_client.return_value = mock_s3_client
        
        downloader = FileDownloader(self.storage_config)
        
        test_content = b'%PDF-1.4\nTest PDF content\n%%EOF'
        s3_key = 'test-retry.pdf'
        
        with patch('time.sleep'):  # Speed up test by mocking sleep
            result = downloader.upload_to_s3(test_content, s3_key)
        
        assert result is True
        assert mock_s3_client.put_object.call_count == 3
    
    @patch('downloader.boto3.client')
    def test_s3_upload_max_retries_exceeded(self, mock_boto3_client):
        """Test S3 upload when max retries are exceeded"""
        mock_s3_client = Mock()
        mock_s3_client.put_object.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable'}}, 'PutObject'
        )
        mock_boto3_client.return_value = mock_s3_client
        
        downloader = FileDownloader(self.storage_config)
        
        test_content = b'%PDF-1.4\nTest PDF content\n%%EOF'
        s3_key = 'test-max-retries.pdf'
        
        with patch('time.sleep'):  # Speed up test
            result = downloader.upload_to_s3(test_content, s3_key)
        
        assert result is False
        assert mock_s3_client.put_object.call_count == 3  # Max retries
    
    def test_s3_upload_without_client(self):
        """Test S3 upload when client is not available"""
        # Create downloader without S3 client
        storage_config = StorageConfig(s3_enabled=False)
        downloader = FileDownloader(storage_config)
        
        test_content = b'%PDF-1.4\nTest PDF content\n%%EOF'
        s3_key = 'test-no-client.pdf'
        
        result = downloader.upload_to_s3(test_content, s3_key)
        
        assert result is False


class TestS3KeyGeneration:
    """Test S3 key generation and organization"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_s3_key_with_prefix_and_department(self):
        """Test S3 key generation with prefix and department organization"""
        storage_config = StorageConfig(
            local_path=self.temp_dir,
            organize_by_department=True,
            s3_enabled=True,
            s3_bucket='test-bucket',
            s3_prefix='hk-government-pdfs/'
        )
        
        downloader = FileDownloader(storage_config)
        
        s3_key = downloader._get_s3_key('test-document.pdf', 'Buildings Department')
        
        expected_key = 'hk-government-pdfs/buildings-department/test-document.pdf'
        assert s3_key == expected_key
    
    def test_s3_key_without_prefix(self):
        """Test S3 key generation without prefix"""
        storage_config = StorageConfig(
            local_path=self.temp_dir,
            organize_by_department=True,
            s3_enabled=True,
            s3_bucket='test-bucket',
            s3_prefix=None
        )
        
        downloader = FileDownloader(storage_config)
        
        s3_key = downloader._get_s3_key('test-document.pdf', 'Labour Department')
        
        expected_key = 'labour-department/test-document.pdf'
        assert s3_key == expected_key
    
    def test_s3_key_without_department_organization(self):
        """Test S3 key generation without department organization"""
        storage_config = StorageConfig(
            local_path=self.temp_dir,
            organize_by_department=False,
            s3_enabled=True,
            s3_bucket='test-bucket',
            s3_prefix='pdfs/'
        )
        
        downloader = FileDownloader(storage_config)
        
        s3_key = downloader._get_s3_key('test-document.pdf', 'Any Department')
        
        expected_key = 'pdfs/test-document.pdf'
        assert s3_key == expected_key
    
    def test_s3_key_special_characters_handling(self):
        """Test S3 key generation with special characters in department name"""
        storage_config = StorageConfig(
            local_path=self.temp_dir,
            organize_by_department=True,
            s3_enabled=True,
            s3_bucket='test-bucket',
            s3_prefix='docs/'
        )
        
        downloader = FileDownloader(storage_config)
        
        # Department name with special characters
        s3_key = downloader._get_s3_key('test.pdf', 'Fire & Safety Department (FSD)')
        
        # Should sanitize department name for S3 key
        expected_key = 'docs/fire-safety-department-fsd/test.pdf'
        assert s3_key == expected_key


class TestS3FileExistenceCheck:
    """Test checking file existence in S3"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_config = StorageConfig(
            local_path=self.temp_dir,
            organize_by_department=True,
            s3_enabled=True,
            s3_bucket='test-bucket',
            s3_prefix='pdfs/'
        )
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('downloader.boto3.client')
    def test_s3_file_exists(self, mock_boto3_client):
        """Test checking if file exists in S3"""
        mock_s3_client = Mock()
        mock_s3_client.head_object.return_value = {}  # File exists
        mock_boto3_client.return_value = mock_s3_client
        
        downloader = FileDownloader(self.storage_config)
        
        file_path = os.path.join(self.temp_dir, 'test-dept', 'existing.pdf')
        
        exists = downloader.file_exists(file_path, 'test-dept')
        
        # Should check S3 since local file doesn't exist
        mock_s3_client.head_object.assert_called_once()
        assert exists is True
    
    @patch('downloader.boto3.client')
    def test_s3_file_not_exists(self, mock_boto3_client):
        """Test checking if file doesn't exist in S3"""
        mock_s3_client = Mock()
        mock_s3_client.head_object.side_effect = ClientError(
            {'Error': {'Code': '404'}}, 'HeadObject'
        )
        mock_boto3_client.return_value = mock_s3_client
        
        downloader = FileDownloader(self.storage_config)
        
        file_path = os.path.join(self.temp_dir, 'test-dept', 'nonexistent.pdf')
        
        exists = downloader.file_exists(file_path, 'test-dept')
        
        assert exists is False
    
    @patch('downloader.boto3.client')
    def test_s3_file_check_error(self, mock_boto3_client):
        """Test S3 file existence check with error"""
        mock_s3_client = Mock()
        mock_s3_client.head_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied'}}, 'HeadObject'
        )
        mock_boto3_client.return_value = mock_s3_client
        
        downloader = FileDownloader(self.storage_config)
        
        file_path = os.path.join(self.temp_dir, 'test-dept', 'error.pdf')
        
        exists = downloader.file_exists(file_path, 'test-dept')
        
        # Should return False on error (file assumed not to exist)
        assert exists is False
    
    def test_local_file_takes_precedence(self):
        """Test that local file existence takes precedence over S3"""
        # Create local file
        dept_dir = os.path.join(self.temp_dir, 'test-dept')
        os.makedirs(dept_dir, exist_ok=True)
        local_file = os.path.join(dept_dir, 'local.pdf')
        
        with open(local_file, 'wb') as f:
            f.write(b'%PDF-1.4\nLocal file content\n%%EOF')
        
        with patch('downloader.boto3.client') as mock_boto3_client:
            mock_s3_client = Mock()
            mock_boto3_client.return_value = mock_s3_client
            
            downloader = FileDownloader(self.storage_config)
            
            exists = downloader.file_exists(local_file, 'test-dept')
            
            # Should return True without checking S3
            assert exists is True
            mock_s3_client.head_object.assert_not_called()


class TestS3IntegratedDownload:
    """Test integrated download workflow with S3"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_config = StorageConfig(
            local_path=self.temp_dir,
            organize_by_department=True,
            s3_enabled=True,
            s3_bucket='test-bucket',
            s3_prefix='hk-pdfs/'
        )
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('downloader.boto3.client')
    @patch('downloader.requests.Session')
    def test_download_with_s3_upload(self, mock_session_class, mock_boto3_client):
        """Test complete download workflow with S3 upload"""
        # Mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.put_object.return_value = {}
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock HTTP session
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/pdf'}
        mock_response.iter_content.return_value = [b'%PDF-1.4\n', b'Test content\n', b'%%EOF']
        
        mock_session.head.return_value = mock_response
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        downloader = FileDownloader(self.storage_config)
        
        result = downloader.download_pdf('https://example.com/test.pdf', 'test-department')
        
        # Should succeed
        assert result.success is True
        assert result.file_size > 0
        
        # Should have uploaded to S3
        mock_s3_client.put_object.assert_called_once()
        
        # Verify S3 upload parameters
        call_args = mock_s3_client.put_object.call_args
        assert call_args[1]['Bucket'] == 'test-bucket'
        assert 'hk-pdfs/test-department/' in call_args[1]['Key']
        assert call_args[1]['ContentType'] == 'application/pdf'
    
    @patch('downloader.boto3.client')
    @patch('downloader.requests.Session')
    def test_download_s3_only_mode(self, mock_session_class, mock_boto3_client):
        """Test download with S3-only storage (no local files)"""
        # Configure for S3-only storage
        s3_only_config = StorageConfig(
            local_path=None,  # No local storage
            organize_by_department=True,
            s3_enabled=True,
            s3_bucket='test-bucket'
        )
        
        # Mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.put_object.return_value = {}
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock HTTP session
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/pdf'}
        mock_response.iter_content.return_value = [b'%PDF-1.4\nS3 only content\n%%EOF']
        
        mock_session.head.return_value = mock_response
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        downloader = FileDownloader(s3_only_config)
        
        result = downloader.download_pdf('https://example.com/s3only.pdf', 'test-dept')
        
        # Should succeed with S3-only storage
        assert result.success is True
        assert result.file_path.startswith('s3://')
        
        # Should have uploaded to S3
        mock_s3_client.put_object.assert_called_once()
    
    @patch('downloader.boto3.client')
    @patch('downloader.requests.Session')
    def test_download_s3_failure_local_success(self, mock_session_class, mock_boto3_client):
        """Test download when S3 upload fails but local save succeeds"""
        # Mock S3 client that fails
        mock_s3_client = Mock()
        mock_s3_client.put_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied'}}, 'PutObject'
        )
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock HTTP session
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/pdf'}
        mock_response.iter_content.return_value = [b'%PDF-1.4\nLocal fallback\n%%EOF']
        
        mock_session.head.return_value = mock_response
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        downloader = FileDownloader(self.storage_config)
        
        result = downloader.download_pdf('https://example.com/fallback.pdf', 'test-dept')
        
        # Should succeed with local storage despite S3 failure
        assert result.success is True
        assert os.path.exists(result.file_path)  # Local file should exist
        
        # S3 upload should have been attempted
        mock_s3_client.put_object.assert_called()


class TestS3ConfigurationValidation:
    """Test S3 configuration validation"""
    
    def test_s3_config_validation_missing_bucket(self):
        """Test S3 configuration validation with missing bucket"""
        storage_config = StorageConfig(
            s3_enabled=True,
            s3_bucket=None  # Missing bucket
        )
        
        # Should handle missing bucket gracefully
        downloader = FileDownloader(storage_config)
        
        # S3 operations should fail gracefully
        result = downloader.upload_to_s3(b'test', 'test.pdf')
        assert result is False
    
    def test_s3_config_validation_empty_bucket(self):
        """Test S3 configuration validation with empty bucket name"""
        storage_config = StorageConfig(
            s3_enabled=True,
            s3_bucket=''  # Empty bucket name
        )
        
        downloader = FileDownloader(storage_config)
        
        # S3 operations should fail gracefully
        result = downloader.upload_to_s3(b'test', 'test.pdf')
        assert result is False
    
    def test_s3_config_with_valid_settings(self):
        """Test S3 configuration with all valid settings"""
        storage_config = StorageConfig(
            local_path='./downloads',
            organize_by_department=True,
            s3_enabled=True,
            s3_bucket='valid-bucket-name',
            s3_prefix='hk-government-docs/'
        )
        
        # Configuration should be valid
        assert storage_config.s3_enabled is True
        assert storage_config.s3_bucket == 'valid-bucket-name'
        assert storage_config.s3_prefix == 'hk-government-docs/'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])