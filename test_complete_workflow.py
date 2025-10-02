#!/usr/bin/env python3
"""
Complete Workflow Test for HK PDF Crawler

This test validates the entire crawling workflow using both input methods
and ensures all components work together correctly.
"""

import os
import sys
import tempfile
import shutil
import json
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config, create_config_from_markdown
from crawler import PDFCrawler
from utils import setup_logging


def create_test_markdown():
    """Create a test markdown file with sample URLs"""
    markdown_content = """# Test Government Department PDF Resources

## 1. Buildings Department (BD):
1. **CoP**: https://www.bd.gov.hk/en/resources/codes-and-references/codes-and-design-manuals/index.html
2. **PNAP**: https://www.bd.gov.hk/en/resources/codes-and-references/practice-notes-and-circular-letters/index_pnap.html

## 2. Labour Department (LD):
1. **OSH Legislation**: https://www.labour.gov.hk/eng/legislat/contentB3.htm
2. **Occupational Safety**: https://www.labour.gov.hk/eng/public/content2_8.htm
"""
    return markdown_content


def create_test_yaml():
    """Create a test YAML configuration"""
    yaml_content = """departments:
  buildings_department:
    name: "Buildings Department"
    seed_urls:
      - "https://www.bd.gov.hk/en/resources/codes-and-references/codes-and-design-manuals/index.html"
    max_depth: 1
    max_pages: 10
    time_limit: 300

  labour_department:
    name: "Labour Department"
    seed_urls:
      - "https://www.labour.gov.hk/eng/public/content2_8.htm"
    max_depth: 1
    max_pages: 10
    time_limit: 300

settings:
  delay_between_requests: 2.0
  max_concurrent_downloads: 1
  respect_robots_txt: true
  user_agent: "HK-PDF-Crawler-Test/1.0"
  enable_browser_automation: false
  request_timeout: 30

storage:
  local_path: "./test_downloads"
  organize_by_department: true
  s3_enabled: false
"""
    return yaml_content


def test_markdown_parsing():
    """Test markdown file parsing"""
    print("Testing markdown parsing...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(create_test_markdown())
        markdown_file = f.name
    
    try:
        config = create_config_from_markdown(markdown_file)
        
        # Validate configuration
        assert len(config.departments) >= 2, "Should parse at least 2 departments"
        assert 'buildings_department' in config.departments, "Should find Buildings Department"
        assert 'labour_department' in config.departments, "Should find Labour Department"
        
        bd_config = config.departments['buildings_department']
        assert len(bd_config.seed_urls) >= 2, "Buildings Department should have at least 2 URLs"
        assert bd_config.name == "Buildings Department", "Department name should be parsed correctly"
        
        print("✅ Markdown parsing test passed")
        return True
        
    except Exception as e:
        print(f"❌ Markdown parsing test failed: {e}")
        return False
    finally:
        os.unlink(markdown_file)


def test_yaml_parsing():
    """Test YAML configuration parsing"""
    print("Testing YAML parsing...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(create_test_yaml())
        yaml_file = f.name
    
    try:
        config = load_config(yaml_file)
        
        # Validate configuration
        assert len(config.departments) == 2, "Should parse exactly 2 departments"
        assert config.settings.delay_between_requests == 2.0, "Settings should be parsed correctly"
        assert config.storage.local_path == "./test_downloads", "Storage config should be parsed"
        
        print("✅ YAML parsing test passed")
        return True
        
    except Exception as e:
        print(f"❌ YAML parsing test failed: {e}")
        return False
    finally:
        os.unlink(yaml_file)


def test_dry_run_analysis():
    """Test dry-run analysis functionality"""
    print("Testing dry-run analysis...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(create_test_yaml())
        yaml_file = f.name
    
    try:
        config = load_config(yaml_file)
        crawler = PDFCrawler(config)
        
        # Run dry-run analysis
        report = crawler.dry_run(['buildings_department'])
        
        # Validate report
        assert len(report.department_analyses) == 1, "Should analyze 1 department"
        assert report.total_estimated_pdfs >= 0, "Should estimate PDF count"
        assert report.estimated_duration >= 0, "Should estimate duration"
        
        analysis = report.department_analyses[0]
        assert analysis.department == "Buildings Department", "Department name should match"
        assert analysis.seed_urls_total == 1, "Should have 1 seed URL"
        
        print("✅ Dry-run analysis test passed")
        return True
        
    except Exception as e:
        print(f"❌ Dry-run analysis test failed: {e}")
        return False
    finally:
        os.unlink(yaml_file)


def test_file_utilities():
    """Test utility functions"""
    print("Testing utility functions...")
    
    try:
        from utils import (
            sanitize_filename, extract_domain, is_valid_url, 
            format_file_size, format_duration, is_government_domain
        )
        
        # Test filename sanitization
        result = sanitize_filename("test<>file.pdf")
        assert "_" in result, f"Expected sanitized filename, got: {result}"
        
        result = sanitize_filename("")
        assert "unnamed_file" in result, f"Expected unnamed_file, got: {result}"
        
        # Test domain extraction
        result = extract_domain("https://www.bd.gov.hk/path")
        assert result in ["bd.gov.hk", "www.bd.gov.hk"], f"Expected bd.gov.hk or www.bd.gov.hk, got: {result}"
        
        result = extract_domain("invalid")
        assert result == "", f"Expected empty string, got: {result}"
        
        # Test URL validation
        result = is_valid_url("https://www.bd.gov.hk/")
        assert result == True, f"Expected True, got: {result}"
        
        result = is_valid_url("not-a-url")
        assert result == False, f"Expected False, got: {result}"
        
        # Test file size formatting
        result = format_file_size(1024)
        assert result == "1.0 KB", f"Expected '1.0 KB', got: {result}"
        
        result = format_file_size(1048576)
        assert result == "1.0 MB", f"Expected '1.0 MB', got: {result}"
        
        # Test duration formatting
        result = format_duration(65)
        assert result == "1m 5s", f"Expected '1m 5s', got: {result}"
        
        result = format_duration(3665)
        assert result == "1h 1m 5s", f"Expected '1h 1m 5s', got: {result}"
        
        # Test government domain detection
        result = is_government_domain("https://www.bd.gov.hk/")
        assert result == True, f"Expected True, got: {result}"
        
        result = is_government_domain("https://www.google.com/")
        assert result == False, f"Expected False, got: {result}"
        
        print("✅ Utility functions test passed")
        return True
        
    except Exception as e:
        print(f"❌ Utility functions test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_configuration_validation():
    """Test configuration validation"""
    print("Testing configuration validation...")
    
    try:
        # Test invalid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content:")
            invalid_yaml = f.name
        
        try:
            load_config(invalid_yaml)
            print("❌ Should have failed on invalid YAML")
            return False
        except Exception:
            pass  # Expected to fail
        finally:
            os.unlink(invalid_yaml)
        
        # Test missing departments
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("settings:\n  delay_between_requests: 1.0")
            no_deps_yaml = f.name
        
        try:
            load_config(no_deps_yaml)
            print("❌ Should have failed on missing departments")
            return False
        except ValueError:
            pass  # Expected to fail
        finally:
            os.unlink(no_deps_yaml)
        
        print("✅ Configuration validation test passed")
        return True
        
    except Exception as e:
        print(f"❌ Configuration validation test failed: {e}")
        return False


def test_directory_creation():
    """Test directory creation and cleanup"""
    print("Testing directory creation...")
    
    try:
        from utils import create_directory_safely
        
        test_dir = "./test_temp_directory"
        
        # Test directory creation
        assert create_directory_safely(test_dir) == True
        assert os.path.exists(test_dir) == True
        
        # Test nested directory creation
        nested_dir = os.path.join(test_dir, "nested", "deep")
        assert create_directory_safely(nested_dir) == True
        assert os.path.exists(nested_dir) == True
        
        # Cleanup
        shutil.rmtree(test_dir)
        
        print("✅ Directory creation test passed")
        return True
        
    except Exception as e:
        print(f"❌ Directory creation test failed: {e}")
        return False


def test_json_operations():
    """Test JSON file operations"""
    print("Testing JSON operations...")
    
    try:
        from utils import safe_json_dump, safe_json_load
        
        test_data = {
            "test": "data",
            "number": 123,
            "list": [1, 2, 3],
            "nested": {"key": "value"}
        }
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            json_file = f.name
        
        # Test JSON writing
        assert safe_json_dump(test_data, json_file) == True
        assert os.path.exists(json_file) == True
        
        # Test JSON reading
        loaded_data = safe_json_load(json_file)
        assert loaded_data == test_data
        
        # Cleanup
        os.unlink(json_file)
        
        print("✅ JSON operations test passed")
        return True
        
    except Exception as e:
        print(f"❌ JSON operations test failed: {e}")
        return False


def run_all_tests():
    """Run all tests and report results"""
    print("="*60)
    print("HK PDF CRAWLER - COMPLETE WORKFLOW TEST")
    print("="*60)
    
    # Set up logging for tests
    setup_logging("INFO")
    
    tests = [
        test_markdown_parsing,
        test_yaml_parsing,
        test_dry_run_analysis,
        test_file_utilities,
        test_configuration_validation,
        test_directory_creation,
        test_json_operations
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
        print()
    
    print("="*60)
    print("TEST RESULTS")
    print("="*60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! The crawler is ready to use.")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please check the issues above.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)