#!/usr/bin/env python3
"""
Test Runner for HK PDF Crawler

This script runs all tests for the HK PDF Crawler project, including unit tests,
integration tests, error handling tests, browser automation tests, and S3 tests.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path


def run_command(command, description):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print('='*60)
    
    try:
        result = subprocess.run(command, check=True, capture_output=False)
        print(f"✅ {description} - PASSED")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED (exit code: {e.returncode})")
        return False
    except FileNotFoundError:
        print(f"❌ {description} - FAILED (command not found)")
        return False


def install_test_dependencies():
    """Install test dependencies"""
    print("Installing test dependencies...")
    
    dependencies = [
        'pytest>=7.0.0',
        'pytest-cov>=4.0.0',
        'responses>=0.23.0',
        'moto>=4.2.0',  # For mocking AWS services
        'selenium>=4.0.0',
        'beautifulsoup4>=4.11.0',
        'requests>=2.28.0',
        'pyyaml>=6.0',
        'boto3>=1.26.0',
        'tqdm>=4.64.0'
    ]
    
    for dep in dependencies:
        command = [sys.executable, '-m', 'pip', 'install', dep]
        if not run_command(command, f"Installing {dep}"):
            print(f"Warning: Failed to install {dep}")
    
    print("✅ Test dependencies installation completed")


def run_unit_tests():
    """Run unit tests"""
    command = [
        sys.executable, '-m', 'pytest', 
        'test_unit_core.py',
        '-v',
        '--tb=short',
        '--cov=.',
        '--cov-report=term-missing'
    ]
    return run_command(command, "Unit Tests (Core Functions)")


def run_integration_tests():
    """Run integration tests with mocked HTTP requests"""
    command = [
        sys.executable, '-m', 'pytest',
        'test_integration_mocked.py',
        '-v',
        '--tb=short'
    ]
    return run_command(command, "Integration Tests (Mocked HTTP)")


def run_end_to_end_tests():
    """Run end-to-end tests"""
    command = [
        sys.executable, '-m', 'pytest',
        'test_end_to_end.py',
        '-v',
        '--tb=short'
    ]
    return run_command(command, "End-to-End Tests")


def run_error_handling_tests():
    """Run error handling tests"""
    command = [
        sys.executable, '-m', 'pytest',
        'test_error_handling.py',
        '-v',
        '--tb=short'
    ]
    return run_command(command, "Error Handling Tests")


def run_browser_tests():
    """Run browser automation tests"""
    command = [
        sys.executable, '-m', 'pytest',
        'test_browser_automation.py',
        '-v',
        '--tb=short'
    ]
    return run_command(command, "Browser Automation Tests")


def run_s3_tests():
    """Run S3 integration tests"""
    command = [
        sys.executable, '-m', 'pytest',
        'test_s3_integration.py',
        '-v',
        '--tb=short'
    ]
    return run_command(command, "S3 Integration Tests")


def run_existing_tests():
    """Run existing test files"""
    existing_tests = [
        'test_comprehensive.py',
        'test_integration.py',
        'test_crawler_integration.py',
        'test_concurrency.py',
        'test_advanced_features.py',
        'test_reporter.py'
    ]
    
    results = []
    for test_file in existing_tests:
        if os.path.exists(test_file):
            command = [sys.executable, '-m', 'pytest', test_file, '-v', '--tb=short']
            success = run_command(command, f"Existing Tests ({test_file})")
            results.append(success)
        else:
            print(f"⚠️  Test file not found: {test_file}")
    
    return all(results) if results else True


def run_all_tests():
    """Run all tests"""
    print("🚀 Starting comprehensive test suite for HK PDF Crawler")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    
    test_functions = [
        run_unit_tests,
        run_integration_tests,
        run_end_to_end_tests,
        run_error_handling_tests,
        run_browser_tests,
        run_s3_tests,
        run_existing_tests
    ]
    
    results = []
    for test_func in test_functions:
        try:
            success = test_func()
            results.append(success)
        except Exception as e:
            print(f"❌ Error running {test_func.__name__}: {e}")
            results.append(False)
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print('='*60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if all(results):
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False


def run_quick_tests():
    """Run a quick subset of tests"""
    print("🏃 Running quick test suite...")
    
    command = [
        sys.executable, '-m', 'pytest',
        'test_unit_core.py',
        'test_integration_mocked.py',
        '-v',
        '--tb=line',
        '-x'  # Stop on first failure
    ]
    
    return run_command(command, "Quick Tests (Unit + Integration)")


def run_coverage_report():
    """Generate detailed coverage report"""
    print("📊 Generating coverage report...")
    
    # Run tests with coverage
    command = [
        sys.executable, '-m', 'pytest',
        '--cov=.',
        '--cov-report=html',
        '--cov-report=term',
        '--cov-report=xml',
        'test_unit_core.py',
        'test_integration_mocked.py'
    ]
    
    success = run_command(command, "Coverage Report Generation")
    
    if success:
        print("\n📈 Coverage reports generated:")
        print("  - HTML: htmlcov/index.html")
        print("  - XML: coverage.xml")
        print("  - Terminal output above")
    
    return success


def check_test_environment():
    """Check if test environment is properly set up"""
    print("🔍 Checking test environment...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return False
    
    print(f"✅ Python version: {sys.version}")
    
    # Check required modules
    required_modules = [
        'pytest', 'requests', 'beautifulsoup4', 'selenium', 
        'yaml', 'boto3', 'tqdm'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module} available")
        except ImportError:
            missing_modules.append(module)
            print(f"❌ {module} missing")
    
    if missing_modules:
        print(f"\n⚠️  Missing modules: {', '.join(missing_modules)}")
        print("Run with --install-deps to install missing dependencies")
        return False
    
    # Check if core modules exist
    core_modules = [
        'config.py', 'discovery.py', 'downloader.py', 
        'browser.py', 'crawler.py', 'models.py', 'utils.py'
    ]
    
    missing_files = []
    for module in core_modules:
        if not os.path.exists(module):
            missing_files.append(module)
            print(f"❌ {module} missing")
        else:
            print(f"✅ {module} found")
    
    if missing_files:
        print(f"\n⚠️  Missing core modules: {', '.join(missing_files)}")
        return False
    
    print("✅ Test environment check passed")
    return True


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description='HK PDF Crawler Test Runner')
    parser.add_argument('--install-deps', action='store_true', 
                       help='Install test dependencies')
    parser.add_argument('--quick', action='store_true',
                       help='Run quick test suite only')
    parser.add_argument('--coverage', action='store_true',
                       help='Generate coverage report')
    parser.add_argument('--check-env', action='store_true',
                       help='Check test environment setup')
    parser.add_argument('--unit', action='store_true',
                       help='Run unit tests only')
    parser.add_argument('--integration', action='store_true',
                       help='Run integration tests only')
    parser.add_argument('--e2e', action='store_true',
                       help='Run end-to-end tests only')
    parser.add_argument('--errors', action='store_true',
                       help='Run error handling tests only')
    parser.add_argument('--browser', action='store_true',
                       help='Run browser automation tests only')
    parser.add_argument('--s3', action='store_true',
                       help='Run S3 integration tests only')
    
    args = parser.parse_args()
    
    if args.install_deps:
        install_test_dependencies()
        return
    
    if args.check_env:
        success = check_test_environment()
        sys.exit(0 if success else 1)
    
    # Check environment before running tests
    if not check_test_environment():
        print("\n❌ Environment check failed. Run --check-env for details.")
        sys.exit(1)
    
    success = True
    
    if args.quick:
        success = run_quick_tests()
    elif args.coverage:
        success = run_coverage_report()
    elif args.unit:
        success = run_unit_tests()
    elif args.integration:
        success = run_integration_tests()
    elif args.e2e:
        success = run_end_to_end_tests()
    elif args.errors:
        success = run_error_handling_tests()
    elif args.browser:
        success = run_browser_tests()
    elif args.s3:
        success = run_s3_tests()
    else:
        # Run all tests by default
        success = run_all_tests()
    
    if success:
        print("\n🎉 Testing completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Testing failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()