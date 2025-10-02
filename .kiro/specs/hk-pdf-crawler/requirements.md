# Requirements Document

## Introduction

This feature implements a Python script-based PDF crawler that systematically downloads PDF documents from Hong Kong government department websites. The crawler will process multiple department URLs, discover PDF links, download the files, and organize them in a structured directory format. This replaces the previously planned complex cloud architecture with a simple, local Python solution.

## Requirements

### Requirement 1

**User Story:** As a researcher, I want to comprehensively discover and download only PDF documents from HK government department websites, so that I can have a complete local collection of PDFs without other file types.

#### Acceptance Criteria

1. WHEN the script is executed THEN the system SHALL crawl all department URLs listed in the configuration
2. WHEN crawling a page THEN the system SHALL identify and filter only PDF-related links
3. WHEN discovering links THEN the system SHALL use multiple methods to identify PDF files (URL patterns, link text, file extensions)
4. WHEN following navigation THEN the system SHALL follow pagination, "View All", "More Results", and similar elements only if they lead to PDF content
5. WHEN encountering search functionality THEN the system SHALL search specifically for PDF documents using appropriate keywords
6. WHEN a PDF link is discovered THEN the system SHALL validate the link before attempting download
7. WHEN a PDF link is validated THEN the system SHALL download the PDF file to the appropriate directory
8. WHEN crawling depth is configured THEN the system SHALL respect maximum depth limits to avoid infinite crawling
9. WHEN visiting URLs THEN the system SHALL maintain a visited URL cache to prevent infinite loops
10. WHEN crawling time exceeds configured limits THEN the system SHALL stop discovery and proceed with found PDFs
11. IF a PDF already exists locally THEN the system SHALL skip downloading unless forced to update

### Requirement 2

**User Story:** As a user, I want the crawler to accurately identify and target only PDF files, so that it doesn't waste time downloading other document types or non-document files.

#### Acceptance Criteria

1. WHEN scanning links THEN the system SHALL check for .pdf file extensions in URLs
2. WHEN examining link attributes THEN the system SHALL check href attributes, data-* attributes, and onclick handlers for PDF indicators
3. WHEN analyzing link text THEN the system SHALL identify PDF-related keywords (PDF, download, document, etc.)
4. WHEN checking MIME types THEN the system SHALL verify content-type headers indicate application/pdf
5. WHEN encountering generic download links THEN the system SHALL perform HEAD requests to determine actual file type
6. WHEN finding embedded PDF viewers THEN the system SHALL extract the actual PDF source URLs
7. WHEN discovering file links THEN the system SHALL exclude non-PDF formats (DOC, XLS, PPT, HTML, etc.)
8. WHEN link analysis is ambiguous THEN the system SHALL use multiple validation methods before proceeding

### Requirement 3

**User Story:** As a user, I want the crawler to handle interactive website elements that are required to access PDFs, so that I can download documents that require button clicks or form interactions.

#### Acceptance Criteria

1. WHEN PDFs require button clicks THEN the system SHALL use browser automation to simulate user interactions
2. WHEN download links are behind JavaScript events THEN the system SHALL execute the necessary JavaScript to reveal download URLs
3. WHEN forms need to be submitted THEN the system SHALL automatically fill and submit required forms (like terms acceptance)
4. WHEN modal dialogs or popups appear THEN the system SHALL handle them appropriately to proceed with downloads
5. WHEN multi-step navigation is required THEN the system SHALL follow the complete workflow to reach PDF download links

### Requirement 4

**User Story:** As a user, I want to verify that discovered PDF links are actually downloadable and valid, so that I don't waste time on broken or inaccessible links.

#### Acceptance Criteria

1. WHEN a PDF link is discovered THEN the system SHALL perform a HEAD request to check if the resource exists
2. WHEN checking PDF accessibility THEN the system SHALL verify the content-type header indicates a PDF file
3. WHEN a PDF link returns an error THEN the system SHALL log the error and skip the download
4. WHEN downloading a PDF THEN the system SHALL verify the downloaded file is a valid PDF format
5. WHEN a downloaded file is corrupted THEN the system SHALL retry the download up to a configured number of times
6. WHEN PDF validation fails THEN the system SHALL remove the invalid file and log the failure
7. WHEN encountering redirect chains THEN the system SHALL follow redirects up to a reasonable limit

### Requirement 5

**User Story:** As a user, I want the downloaded PDFs to be organized by department and document type, so that I can easily locate specific documents.

#### Acceptance Criteria

1. WHEN downloading PDFs THEN the system SHALL create a directory structure organized by department name
2. WHEN saving PDFs THEN the system SHALL use meaningful filenames based on document titles or URLs
3. WHEN organizing files THEN the system SHALL create subdirectories for different document types (CoP, PNAP, etc.) where applicable
4. WHEN duplicate filenames exist THEN the system SHALL handle naming conflicts appropriately

### Requirement 6

**User Story:** As a user, I want to optionally upload downloaded PDFs to Amazon S3 for cloud storage and backup, so that I can access the documents from anywhere and have reliable backup.

#### Acceptance Criteria

1. WHEN S3 integration is enabled THEN the system SHALL upload PDFs to a configured S3 bucket
2. WHEN uploading to S3 THEN the system SHALL maintain the same directory structure as local storage
3. WHEN S3 upload fails THEN the system SHALL retry with exponential backoff and log failures
4. WHEN configuring S3 THEN the system SHALL support AWS credentials via environment variables, profiles, or IAM roles
5. WHEN uploading to S3 THEN the system SHALL optionally set appropriate metadata (content-type, department tags, etc.)
6. WHEN S3 storage is used THEN the system SHALL optionally skip local storage to save disk space
7. WHEN checking for existing files THEN the system SHALL check both local and S3 storage based on configuration

### Requirement 7

**User Story:** As a user, I want the crawler to use multiple discovery strategies to find all available PDFs, so that no documents are missed due to limited seed URLs.

#### Acceptance Criteria

1. WHEN crawling a domain THEN the system SHALL discover and follow sitemap.xml files if available
2. WHEN encountering archive or historical sections THEN the system SHALL explore these areas for additional PDFs
3. WHEN finding category or topic-based navigation THEN the system SHALL follow all relevant categories
4. WHEN discovering RSS feeds or news sections THEN the system SHALL check these for PDF announcements
5. WHEN encountering search forms THEN the system SHALL optionally perform keyword searches for common document types
6. WHEN finding "All Publications" or similar comprehensive listing pages THEN the system SHALL prioritize these for complete coverage

### Requirement 8

**User Story:** As a user, I want to configure time limits and resource constraints to prevent runaway crawling processes, so that the crawler completes in a reasonable timeframe.

#### Acceptance Criteria

1. WHEN configuring time limits THEN the system SHALL allow setting maximum crawl time per domain
2. WHEN configuring resource limits THEN the system SHALL allow setting maximum pages to visit per domain
3. WHEN configuring URL limits THEN the system SHALL allow setting maximum URLs to queue for processing
4. WHEN time or resource limits are reached THEN the system SHALL gracefully stop discovery and report what was found
5. WHEN detecting potential infinite loops THEN the system SHALL implement circuit breakers to stop problematic crawling patterns
6. WHEN crawling is taking too long THEN the system SHALL provide progress updates and allow user interruption

### Requirement 9

**User Story:** As a user, I want to configure which departments and document types to crawl, so that I can customize the scope of the download process.

#### Acceptance Criteria

1. WHEN starting the script THEN the system SHALL read configuration from the provided markdown file or configuration
2. WHEN processing departments THEN the system SHALL allow selective crawling of specific departments
3. IF configuration specifies document type filters THEN the system SHALL only download matching document types
4. WHEN configuration is invalid THEN the system SHALL provide clear error messages
5. WHEN configuring discovery depth THEN the system SHALL allow setting maximum crawl depth per domain
6. WHEN configuring discovery scope THEN the system SHALL allow enabling/disabling different discovery strategies

### Requirement 10

**User Story:** As a user, I want to see comprehensive statistics and reporting about the crawling process, so that I can understand the effectiveness and completeness of each crawl session.

#### Acceptance Criteria

1. WHEN crawling starts THEN the system SHALL track statistics for each input URL/department
2. WHEN discovering PDFs THEN the system SHALL count total PDFs discovered per input URL
3. WHEN validating PDFs THEN the system SHALL count how many PDFs are downloadable vs inaccessible
4. WHEN downloading PDFs THEN the system SHALL track successful downloads, failures, and skipped files
5. WHEN crawling completes THEN the system SHALL generate a detailed report showing:
   - Total URLs crawled per department
   - Total PDFs discovered per department
   - Total PDFs successfully downloaded per department
   - Total PDFs failed to download with reasons
   - Total PDFs skipped (already exists)
   - Download success rate percentage
   - Time taken per department
   - File size statistics
6. WHEN generating reports THEN the system SHALL save statistics to a CSV/JSON file for analysis
7. WHEN running incremental updates THEN the system SHALL compare statistics with previous runs

### Requirement 11

**User Story:** As a user, I want to see real-time progress and logging information during the crawling process, so that I can monitor the current status and troubleshoot issues as they occur.

#### Acceptance Criteria

1. WHEN crawling starts THEN the system SHALL display progress information for each department with live counters
2. WHEN discovering PDFs THEN the system SHALL show real-time counts of PDFs found per department
3. WHEN downloading files THEN the system SHALL display current download progress with file names and success/failure status
4. WHEN errors occur THEN the system SHALL log detailed error information with timestamps and context
5. WHEN rate limiting occurs THEN the system SHALL display wait times and retry attempts
6. WHEN crawling completes THEN the system SHALL display a final summary with key statistics

### Requirement 12

**User Story:** As a user, I want the crawler to handle website restrictions intelligently while still accessing publicly available PDFs, so that I can download documents that are legitimately accessible.

#### Acceptance Criteria

1. WHEN encountering basic bot detection THEN the system SHALL use realistic browser headers and user-agent strings
2. WHEN facing JavaScript-rendered content THEN the system SHALL optionally use browser automation (Selenium) to access dynamic content
3. WHEN rate limiting occurs THEN the system SHALL implement intelligent delays and retry mechanisms
4. WHEN encountering CAPTCHA or advanced protection THEN the system SHALL log the restriction and optionally pause for manual intervention
5. WHEN robots.txt exists THEN the system SHALL check it but allow override options for publicly accessible government documents

### Requirement 13

**User Story:** As a user, I want the crawler to handle network issues and website changes gracefully, so that temporary problems don't break the entire process.

#### Acceptance Criteria

1. WHEN network timeouts occur THEN the system SHALL retry downloads with exponential backoff
2. WHEN HTTP errors are encountered THEN the system SHALL log the error and continue with other downloads
3. WHEN website structure changes THEN the system SHALL handle missing elements gracefully
4. WHEN access is denied or forbidden THEN the system SHALL log the restriction and continue with other sites

### Requirement 14

**User Story:** As a user, I want to run incremental updates to download only new or updated documents, so that I don't need to re-download everything each time.

#### Acceptance Criteria

1. WHEN running in update mode THEN the system SHALL check file modification dates or checksums
2. WHEN a file hasn't changed THEN the system SHALL skip the download
3. WHEN new files are detected THEN the system SHALL download only the new content
4. WHEN tracking changes THEN the system SHALL maintain a record of previously downloaded files

### Requirement 15

**User Story:** As a user, I want to configure advanced crawling techniques to overcome common website restrictions, so that I can access publicly available government PDFs despite technical barriers.

#### Acceptance Criteria

1. WHEN configuring the crawler THEN the system SHALL support multiple user-agent rotation strategies
2. WHEN configuring request handling THEN the system SHALL support session management and cookie handling
3. WHEN configuring browser simulation THEN the system SHALL optionally use headless browser automation for JavaScript-heavy sites
4. WHEN configuring proxy support THEN the system SHALL allow proxy rotation to handle IP-based restrictions
5. WHEN configuring retry logic THEN the system SHALL support exponential backoff and multiple retry strategies
6. WHEN encountering cloudflare or similar protection THEN the system SHALL provide options to use specialized bypass libraries