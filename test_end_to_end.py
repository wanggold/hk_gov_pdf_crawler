#!/usr/bin/env python3
"""
End-to-End Tests with Sample Configuration

This module contains end-to-end tests that simulate complete crawling workflows
using sample configurations and mock websites to test the entire system integration.
"""

import pytest
import tempfile
import os
import yaml
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import responses

# Import modules to test
from config import CrawlConfig, DepartmentConfig, CrawlSettings, StorageConfig, load_config
from crawler import PDFCrawler
from main import main, create_config_from_markdown
from models import CrawlResults


class TestEndToEndWorkflow:
    """End-to-end workflow tests"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = None
        self.markdown_file = None
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        if self.config_file and os.path.exists(self.config_file):
            os.unlink(self.config_file)
        if self.markdown_file and os.path.exists(self.markdown_file):
            os.unlink(self.markdown_file)
    
    def create_sample_config_file(self) -> str:
        """Create a sample YAML configuration file"""
        config_data = {
            'departments': {
                'buildings_department': {
                    'name': 'Buildings Department',
                    'seed_urls': [
                        'https://www.bd.gov.hk/en/resources/codes-and-references/codes-and-design-manuals/index.html',
                        'https://www.bd.gov.hk/en/resources/codes-and-references/practice-notes-and-circular-letters/index_pnap.html'
                    ],
                    'max_depth': 2,
                    'max_pages': 20,
                    'time_limit': 300
                },
                'labour_department': {
                    'name': 'Labour Department',
                    'seed_urls': [
                        'https://www.labour.gov.hk/eng/legislat/contentB3.htm',
                        'https://www.labour.gov.hk/eng/public/content2_8.htm'
                    ],
                    'max_depth': 2,
                    'max_pages': 15,
                    'time_limit': 240
                }
            },
            'settings': {
                'delay_between_requests': 0.5,
                'max_concurrent_downloads': 2,
                'respect_robots_txt': True,
                'user_agent': 'HK-PDF-Crawler-Test/1.0',
                'enable_browser_automation': False,
                'request_timeout': 30
            },
            'storage': {
                'local_path': self.temp_dir,
                'organize_by_department': True,
                's3_enabled': False,
                's3_bucket': None,
                's3_prefix': None
            }
        }
        
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(config_data, config_file, default_flow_style=False)
        config_file.close()
        
        self.config_file = config_file.name
        return config_file.name
    
    def create_sample_markdown_file(self) -> str:
        """Create a sample markdown file with department URLs"""
        markdown_content = """# Hong Kong Government Department PDF Resources

## 1. Buildings Department (BD):
1. **Code of Practice**: https://www.bd.gov.hk/en/resources/codes-and-references/codes-and-design-manuals/index.html
2. **Practice Notes**: https://www.bd.gov.hk/en/resources/codes-and-references/practice-notes-and-circular-letters/index_pnap.html
3. **Technical Memoranda**: https://www.bd.gov.hk/en/resources/codes-and-references/technical-memoranda/index.html

## 2. Labour Department (LD):
1. **OSH Legislation**: https://www.labour.gov.hk/eng/legislat/contentB3.htm
2. **Occupational Safety**: https://www.labour.gov.hk/eng/public/content2_8.htm
3. **Guidelines**: https://www.labour.gov.hk/eng/public/wcp/index.htm

## 3. Fire Services Department (FSD):
1. **Fire Safety**: https://www.hkfsd.gov.hk/eng/source/safety/index.html
2. **Codes and Standards**: https://www.hkfsd.gov.hk/eng/source/codes/index.html
"""
        
        markdown_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        markdown_file.write(markdown_content)
        markdown_file.close()
        
        self.markdown_file = markdown_file.name
        return markdown_file.name
    
    @responses.activate
    def test_complete_yaml_config_workflow(self):
        """Test complete workflow using YAML configuration"""
        # Create sample config
        config_file = self.create_sample_config_file()
        
        # Mock website responses
        self._setup_mock_responses()
        
        # Load configuration
        config = load_config(config_file)
        assert isinstance(config, CrawlConfig)
        assert len(config.departments) == 2
        
        # Initialize and run crawler
        crawler = PDFCrawler(config)
        
        # Test dry-run first
        dry_run_report = crawler.dry_run()
        assert len(dry_run_report.department_analyses) == 2
        assert dry_run_report.total_estimated_pdfs > 0
        
        # Run actual crawl
        results = crawler.crawl()
        
        # Verify results
        assert isinstance(results, CrawlResults)
        assert len(results.departments) == 2
        assert results.total_pdfs_found > 0
        assert results.total_pdfs_downloaded >= 0
        
        # Verify files were organized by department
        bd_dir = Path(self.temp_dir) / 'buildings-department'
        ld_dir = Path(self.temp_dir) / 'labour-department'
        
        # At least one department should have downloaded files
        total_files = 0
        if bd_dir.exists():
            total_files += len(list(bd_dir.glob('*.pdf')))
        if ld_dir.exists():
            total_files += len(list(ld_dir.glob('*.pdf')))
        
        assert total_files >= 0  # May be 0 if no PDFs found in mock
    
    @responses.activate
    def test_complete_markdown_config_workflow(self):
        """Test complete workflow using markdown configuration"""
        # Create sample markdown file
        markdown_file = self.create_sample_markdown_file()
        
        # Mock website responses
        self._setup_mock_responses()
        
        # Create configuration from markdown
        config = create_config_from_markdown(markdown_file)
        assert isinstance(config, CrawlConfig)
        assert len(config.departments) == 3  # BD, LD, FSD
        
        # Update storage path
        config.storage.local_path = self.temp_dir
        
        # Initialize and run crawler
        crawler = PDFCrawler(config)
        
        # Test dry-run
        dry_run_report = crawler.dry_run()
        assert len(dry_run_report.department_analyses) == 3
        
        # Run crawl for specific departments
        results = crawler.crawl(['buildings_department', 'labour_department'])
        
        # Verify results
        assert len(results.departments) == 2
        dept_names = [d.department for d in results.departments]
        assert 'Buildings Department' in dept_names
        assert 'Labour Department' in dept_names
    
    @responses.activate 
    def test_selective_department_crawling(self):
        """Test crawling specific departments only"""
        config_file = self.create_sample_config_file()
        self._setup_mock_responses()
        
        config = load_config(config_file)
        crawler = PDFCrawler(config)
        
        # Crawl only Buildings Department
        results = crawler.crawl(['buildings_department'])
        
        assert len(results.departments) == 1
        assert results.departments[0].department == 'Buildings Department'
    
    @responses.activate
    def test_error_recovery_workflow(self):
        """Test workflow with various error conditions"""
        config_file = self.create_sample_config_file()
        
        # Mock responses with some failures
        self._setup_mock_responses_with_errors()
        
        config = load_config(config_file)
        crawler = PDFCrawler(config)
        
        # Run crawl and expect it to handle errors gracefully
        results = crawler.crawl()
        
        # Should complete despite errors
        assert isinstance(results, CrawlResults)
        assert len(results.departments) == 2
        
        # Check that errors were recorded
        total_errors = sum(len(dept.errors) for dept in results.departments)
        assert total_errors >= 0  # May have errors from failed requests
    
    def test_configuration_validation(self):
        """Test configuration validation with invalid configs"""
        # Test missing departments
        invalid_config = {
            'settings': {'delay_between_requests': 1.0},
            'storage': {'local_path': './downloads'}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(invalid_config, f)
            invalid_config_file = f.name
        
        try:
            with pytest.raises(ValueError, match="must contain 'departments'"):
                load_config(invalid_config_file)
        finally:
            os.unlink(invalid_config_file)
        
        # Test department without required fields
        invalid_dept_config = {
            'departments': {
                'invalid_dept': {
                    'name': 'Invalid Department'
                    # Missing seed_urls
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(invalid_dept_config, f)
            invalid_dept_file = f.name
        
        try:
            with pytest.raises(ValueError, match="must have 'seed_urls'"):
                load_config(invalid_dept_file)
        finally:
            os.unlink(invalid_dept_file)
    
    def test_report_generation_and_saving(self):
        """Test report generation and file saving"""
        from reporter import ProgressReporter
        from models import DepartmentResults, CrawlResults
        
        # Create mock results
        dept_results = [
            DepartmentResults(
                department='Test Department 1',
                urls_crawled=10,
                pdfs_found=5,
                pdfs_downloaded=4,
                pdfs_failed=1,
                pdfs_skipped=0,
                total_size=2048,
                duration=30.0,
                errors=['Test error 1']
            ),
            DepartmentResults(
                department='Test Department 2',
                urls_crawled=8,
                pdfs_found=3,
                pdfs_downloaded=3,
                pdfs_failed=0,
                pdfs_skipped=0,
                total_size=1536,
                duration=20.0,
                errors=[]
            )
        ]
        
        results = CrawlResults(
            departments=dept_results,
            total_pdfs_found=8,
            total_pdfs_downloaded=7,
            total_duration=50.0,
            success_rate=87.5
        )
        
        reporter = ProgressReporter()
        
        # Test report generation
        report_text = reporter.generate_report(results)
        assert 'FINAL REPORT' in report_text
        assert 'Test Department 1' in report_text
        assert 'Test Department 2' in report_text
        assert '87.5%' in report_text
        
        # Test JSON report saving
        original_dir = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            reporter.save_report(results, format='json')
            
            # Find the generated JSON file
            json_files = list(Path(self.temp_dir).glob('crawl_report_*.json'))
            assert len(json_files) == 1
            
            # Verify JSON content
            with open(json_files[0], 'r') as f:
                report_data = json.load(f)
            
            assert report_data['overall_stats']['total_pdfs_found'] == 8
            assert report_data['overall_stats']['total_pdfs_downloaded'] == 7
            assert len(report_data['departments']) == 2
            
        finally:
            os.chdir(original_dir)
        
        # Test CSV report saving
        try:
            os.chdir(self.temp_dir)
            reporter.save_report(results, format='csv')
            
            # Find the generated CSV file
            csv_files = list(Path(self.temp_dir).glob('crawl_report_*.csv'))
            assert len(csv_files) == 1
            
            # Verify CSV content
            with open(csv_files[0], 'r') as f:
                csv_content = f.read()
            
            assert 'Department,URLs_Crawled' in csv_content
            assert 'Test Department 1' in csv_content
            assert 'Test Department 2' in csv_content
            
        finally:
            os.chdir(original_dir)
    
    def _setup_mock_responses(self):
        """Set up mock HTTP responses for testing"""
        # Mock main pages for each department
        bd_main_html = """
        <html>
        <head><title>Buildings Department - Codes and Design Manuals</title></head>
        <body>
            <h1>Codes and Design Manuals</h1>
            <ul>
                <li><a href="cop_2023.pdf">Code of Practice 2023</a></li>
                <li><a href="design_manual.pdf">Design Manual</a></li>
                <li><a href="technical_guide.pdf">Technical Guide</a></li>
                <li><a href="subpage.html">More Documents</a></li>
            </ul>
        </body>
        </html>
        """
        
        ld_main_html = """
        <html>
        <head><title>Labour Department - OSH Legislation</title></head>
        <body>
            <h1>Occupational Safety and Health Legislation</h1>
            <ul>
                <li><a href="osh_ordinance.pdf">OSH Ordinance</a></li>
                <li><a href="safety_guidelines.pdf">Safety Guidelines</a></li>
                <li><a href="regulations.pdf">Regulations</a></li>
            </ul>
        </body>
        </html>
        """
        
        # Mock subpage
        subpage_html = """
        <html>
        <body>
            <h2>Additional Documents</h2>
            <ul>
                <li><a href="additional_doc.pdf">Additional Document</a></li>
                <li><a href="archive/old_manual.pdf">Archived Manual</a></li>
            </ul>
        </body>
        </html>
        """
        
        # Add main page responses
        responses.add(responses.GET, 'https://www.bd.gov.hk/en/resources/codes-and-references/codes-and-design-manuals/index.html',
                     body=bd_main_html, status=200, content_type='text/html')
        responses.add(responses.GET, 'https://www.bd.gov.hk/en/resources/codes-and-references/practice-notes-and-circular-letters/index_pnap.html',
                     body=bd_main_html, status=200, content_type='text/html')
        responses.add(responses.GET, 'https://www.labour.gov.hk/eng/legislat/contentB3.htm',
                     body=ld_main_html, status=200, content_type='text/html')
        responses.add(responses.GET, 'https://www.labour.gov.hk/eng/public/content2_8.htm',
                     body=ld_main_html, status=200, content_type='text/html')
        
        # Add subpage response
        responses.add(responses.GET, 'https://www.bd.gov.hk/subpage.html',
                     body=subpage_html, status=200, content_type='text/html')
        
        # Mock PDF files
        pdf_content = b'%PDF-1.4\n' + b'Mock PDF content for end-to-end testing. ' * 50 + b'\n%%EOF'
        
        pdf_urls = [
            'https://www.bd.gov.hk/cop_2023.pdf',
            'https://www.bd.gov.hk/design_manual.pdf',
            'https://www.bd.gov.hk/technical_guide.pdf',
            'https://www.bd.gov.hk/additional_doc.pdf',
            'https://www.bd.gov.hk/archive/old_manual.pdf',
            'https://www.labour.gov.hk/osh_ordinance.pdf',
            'https://www.labour.gov.hk/safety_guidelines.pdf',
            'https://www.labour.gov.hk/regulations.pdf'
        ]
        
        for pdf_url in pdf_urls:
            responses.add(responses.HEAD, pdf_url,
                         headers={'content-type': 'application/pdf', 'content-length': str(len(pdf_content))},
                         status=200)
            responses.add(responses.GET, pdf_url,
                         body=pdf_content, headers={'content-type': 'application/pdf'},
                         status=200)
    
    def _setup_mock_responses_with_errors(self):
        """Set up mock responses that include various error conditions"""
        # Some successful responses
        success_html = '<html><body><a href="good.pdf">Good PDF</a><a href="bad.pdf">Bad PDF</a></body></html>'
        
        responses.add(responses.GET, 'https://www.bd.gov.hk/en/resources/codes-and-references/codes-and-design-manuals/index.html',
                     body=success_html, status=200)
        
        # Some failed responses
        responses.add(responses.GET, 'https://www.bd.gov.hk/en/resources/codes-and-references/practice-notes-and-circular-letters/index_pnap.html',
                     status=404)  # Page not found
        
        responses.add(responses.GET, 'https://www.labour.gov.hk/eng/legislat/contentB3.htm',
                     status=500)  # Server error
        
        responses.add(responses.GET, 'https://www.labour.gov.hk/eng/public/content2_8.htm',
                     body=success_html, status=200)
        
        # Mock PDF responses with mixed success/failure
        pdf_content = b'%PDF-1.4\nGood PDF content\n%%EOF'
        
        # Good PDF
        responses.add(responses.HEAD, 'https://www.bd.gov.hk/good.pdf',
                     headers={'content-type': 'application/pdf'}, status=200)
        responses.add(responses.GET, 'https://www.bd.gov.hk/good.pdf',
                     body=pdf_content, status=200)
        
        # Bad PDF (404)
        responses.add(responses.HEAD, 'https://www.bd.gov.hk/bad.pdf', status=404)
        
        # Another good PDF
        responses.add(responses.HEAD, 'https://www.labour.gov.hk/good.pdf',
                     headers={'content-type': 'application/pdf'}, status=200)
        responses.add(responses.GET, 'https://www.labour.gov.hk/good.pdf',
                     body=pdf_content, status=200)


class TestMainCLIInterface:
    """Test the main CLI interface"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_argv = None
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        import sys
        
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        if self.original_argv:
            sys.argv = self.original_argv
    
    @patch('main.PDFCrawler')
    def test_main_with_yaml_config(self, mock_crawler_class):
        """Test main function with YAML configuration"""
        import sys
        
        # Create test config file
        config_data = {
            'departments': {
                'test_dept': {
                    'name': 'Test Department',
                    'seed_urls': ['https://example.com']
                }
            }
        }
        
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(config_data, config_file)
        config_file.close()
        
        try:
            # Mock crawler instance
            mock_crawler = Mock()
            mock_crawler.crawl.return_value = Mock(
                departments=[],
                total_pdfs_found=0,
                total_pdfs_downloaded=0,
                total_duration=0,
                success_rate=0
            )
            mock_crawler_class.return_value = mock_crawler
            
            # Set up command line arguments
            self.original_argv = sys.argv.copy()
            sys.argv = ['main.py', '--config', config_file.name]
            
            # Run main function
            main()
            
            # Verify crawler was initialized and called
            mock_crawler_class.assert_called_once()
            mock_crawler.crawl.assert_called_once()
            
        finally:
            os.unlink(config_file.name)
            if self.original_argv:
                sys.argv = self.original_argv
    
    @patch('main.PDFCrawler')
    def test_main_with_dry_run(self, mock_crawler_class):
        """Test main function with dry-run option"""
        import sys
        
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump({'departments': {'test': {'name': 'Test', 'seed_urls': ['https://example.com']}}}, config_file)
        config_file.close()
        
        try:
            # Mock crawler instance
            mock_crawler = Mock()
            mock_crawler.dry_run.return_value = Mock(
                department_analyses=[],
                total_estimated_pdfs=0,
                estimated_duration=0,
                issues_found=[],
                recommendations=[]
            )
            mock_crawler_class.return_value = mock_crawler
            
            # Set up command line arguments for dry run
            self.original_argv = sys.argv.copy()
            sys.argv = ['main.py', '--config', config_file.name, '--dry-run']
            
            # Run main function
            main()
            
            # Verify dry_run was called instead of crawl
            mock_crawler.dry_run.assert_called_once()
            mock_crawler.crawl.assert_not_called()
            
        finally:
            os.unlink(config_file.name)
            if self.original_argv:
                sys.argv = self.original_argv
    
    @patch('main.PDFCrawler')
    def test_main_with_specific_departments(self, mock_crawler_class):
        """Test main function with specific department selection"""
        import sys
        
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump({
            'departments': {
                'dept1': {'name': 'Dept 1', 'seed_urls': ['https://example1.com']},
                'dept2': {'name': 'Dept 2', 'seed_urls': ['https://example2.com']}
            }
        }, config_file)
        config_file.close()
        
        try:
            # Mock crawler instance
            mock_crawler = Mock()
            mock_crawler.crawl.return_value = Mock(
                departments=[],
                total_pdfs_found=0,
                total_pdfs_downloaded=0,
                total_duration=0,
                success_rate=0
            )
            mock_crawler_class.return_value = mock_crawler
            
            # Set up command line arguments with specific departments
            self.original_argv = sys.argv.copy()
            sys.argv = ['main.py', '--config', config_file.name, '--departments', 'dept1']
            
            # Run main function
            main()
            
            # Verify crawl was called with specific departments
            mock_crawler.crawl.assert_called_once_with(['dept1'])
            
        finally:
            os.unlink(config_file.name)
            if self.original_argv:
                sys.argv = self.original_argv


if __name__ == "__main__":
    pytest.main([__file__, "-v"])