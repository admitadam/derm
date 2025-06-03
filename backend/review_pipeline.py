# ai_lit_review_pipeline.py

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
from openai import OpenAI
import os
from functools import wraps
import concurrent.futures
import urllib.parse
import re
import zipfile
import tempfile
from pathlib import Path
import time
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import json

app = Flask(__name__)
CORS(app)

# === Configuration ===
# Add your OpenAI API key here
client = OpenAI(api_key="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")

# API endpoints
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EUROPE_PMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UNPAYWALL_API = "https://api.unpaywall.org/v2/"
UNPAYWALL_EMAIL = "akashla@emory.edu"
SCIHUB_URLS = [
    "https://sci-hub.se/",
    "https://sci-hub.st/",
    "https://sci-hub.ru/"
]

def validate_request(required_fields):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json()
            if not data:
                return jsonify({"error": "No JSON data provided"}), 400
            
            missing_fields = [field for field in required_fields if field not in data or not data[field]]
            if missing_fields:
                return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def handle_api_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Error in {func.__name__}: {str(e)}")  # Server-side logging
            return jsonify({
                "error": f"Server error: {str(e)}",
                "function": func.__name__,
                "error_type": type(e).__name__
            }), 500
    return wrapper

# === Step 1: Generate PubMed Search String ===
@app.route("/generate-search-string", methods=["POST"])
@validate_request(["question"])
@handle_api_error
def generate_search_string():
    data = request.get_json()
    question = data["question"]

    # Validate question format
    if len(question) < 10:
        return jsonify({"error": "Question must be at least 10 characters long"}), 400
    if not question.strip().endswith("?"):
        return jsonify({"error": "Question must end with a question mark"}), 400

    prompt = f"Convert the following clinical research question into a PubMed-compatible Boolean search string using MeSH terms and operators: '{question}' and don't include any other text."
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a medical librarian helping construct systematic review searches."},
            {"role": "user", "content": prompt}
        ]
    )
    
    search_string = response.choices[0].message.content.strip()
    return jsonify({"search_string": search_string})

@app.route("/generate-abstract", methods=["POST"])
@validate_request(["question"])
@handle_api_error
def generate_abstract():
    data = request.get_json()
    question = data["question"]

    # Validate question format
    if len(question) < 10:
        return jsonify({"error": "Question must be at least 10 characters long"}), 400
    if not question.strip().endswith("?"):
        return jsonify({"error": "Question must end with a question mark"}), 400

    prompt = f"""As an expert academic researcher, generate a structured abstract for a potential literature review that would answer the following research question: '{question}'

The abstract should follow this structure:
1. Background/Context
2. Objective
3. Expected Methods
4. Anticipated Findings
5. Potential Implications

Keep each section concise but informative. Format with clear section headers and line breaks between sections."""
    
    response = client.chat.completions.create(
        model="gpt-4",  # Using GPT-4 for higher quality abstract generation
        messages=[
            {"role": "system", "content": "You are an expert academic researcher specializing in literature reviews and meta-analyses."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,  # Slightly higher temperature for more creative yet focused responses
        max_tokens=1000   # Allow for a detailed abstract
    )
    
    abstract = response.choices[0].message.content.strip()
    return jsonify({"abstract": abstract})

# === Step 2: Search PubMed and return number of results ===
@app.route("/pubmed-search", methods=["POST"])
@validate_request(["search_string"])
@handle_api_error
def pubmed_search():
    data = request.get_json()
    search_string = data["search_string"]

    try:
        print(f"Searching PubMed with query: {search_string}")
        params = {
            "db": "pubmed",
            "term": search_string,
            "retmode": "json"
        }
        print(f"PubMed API params: {params}")
        
        r = requests.get(PUBMED_SEARCH_URL, params=params)
        r.raise_for_status()
        
        results = r.json()
        print(f"PubMed API response: {results}")
        
        if "esearchresult" not in results:
            print(f"Unexpected PubMed response format: {results}")
            return jsonify({"error": "Invalid response from PubMed"}), 500
            
        count = results["esearchresult"].get("count", "0")
        print(f"Found {count} papers in PubMed")
        
        return jsonify({"result_count": int(count)})
        
    except Exception as e:
        print(f"Error in pubmed_search: {str(e)}")
        return jsonify({"error": f"Failed to search PubMed: {str(e)}"}), 500

def transform_publisher_urls(url, doi):
    """Transform URLs based on publisher-specific patterns"""
    if not url or not doi:
        return [url] if url else []
        
    transformed_urls = [url]
    
    try:
        # Extract domain from URL
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        path = parsed_url.path
        
        # Wiley Online Library transformations
        if 'wiley' in domain:
            # Try different Wiley domains
            wiley_domains = [
                'onlinelibrary.wiley.com',
                'febs.onlinelibrary.wiley.com',
                'bpspubs.onlinelibrary.wiley.com'
            ]
            for wiley_domain in wiley_domains:
                # LibKey style: Convert /doi/ to /doi/epdf/
                if '/doi/' in path:
                    epdf_url = url.replace('/doi/', '/doi/epdf/')
                    if epdf_url not in transformed_urls:
                        transformed_urls.append(epdf_url)
                
                # Direct PDF URL format
                pdf_url = f"https://{wiley_domain}/doi/pdf/{doi}"
                if pdf_url not in transformed_urls:
                    transformed_urls.append(pdf_url)
                
                # Full text URL format
                full_url = f"https://{wiley_domain}/doi/full/{doi}"
                if full_url not in transformed_urls:
                    transformed_urls.append(full_url)
        
        # Science Direct transformations
        if 'sciencedirect' in domain:
            # Try both PDF and full text URLs
            pdf_url = url.replace('/article/', '/pdf/')
            if pdf_url not in transformed_urls:
                transformed_urls.append(pdf_url)
            # Add /pdfft if not present
            if not pdf_url.endswith('/pdfft'):
                pdfft_url = pdf_url.rstrip('/') + '/pdfft'
                transformed_urls.append(pdfft_url)
        
        # Springer transformations
        if 'springer' in domain:
            # Try /pdf and /epub formats
            if '/chapter/' in path or '/article/' in path:
                pdf_url = url.rstrip('/') + '.pdf'
                transformed_urls.append(pdf_url)
                epub_url = url.rstrip('/') + '.epub'
                transformed_urls.append(epub_url)
        
        # JAAD transformations
        if 'jaad.org' in domain:
            # Try different URL patterns
            article_id = url.split('/')[-1].replace('.pdf', '')
            patterns = [
                f"http://www.jaad.org/article/{article_id}/pdf",
                f"https://www.jaad.org/article/{article_id}/pdf",
                f"http://www.jaad.org/pdf/{article_id}",
                f"https://www.jaad.org/pdf/{article_id}"
            ]
            for pattern in patterns:
                if pattern not in transformed_urls:
                    transformed_urls.append(pattern)
                    
        # Taylor & Francis transformations
        if 'tandfonline' in domain:
            if '/doi/' in path:
                # Try /pdf version
                pdf_url = url.replace('/doi/', '/doi/pdf/')
                if pdf_url not in transformed_urls:
                    transformed_urls.append(pdf_url)
                # Try /epub version
                epub_url = url.replace('/doi/', '/doi/epub/')
                if epub_url not in transformed_urls:
                    transformed_urls.append(epub_url)
                    
        # Oxford Academic transformations
        if 'academic.oup' in domain:
            if '/doi/' in path:
                pdf_url = url.replace('/doi/', '/doi/pdf/')
                if pdf_url not in transformed_urls:
                    transformed_urls.append(pdf_url)
                    
        # SAGE transformations
        if 'sagepub' in domain:
            if '/doi/' in path:
                pdf_url = url.replace('/doi/', '/doi/pdf/')
                if pdf_url not in transformed_urls:
                    transformed_urls.append(pdf_url)
                    
        print(f"\nTransformed URLs for {domain}:")
        for t_url in transformed_urls:
            print(f"- {t_url}")
            
    except Exception as e:
        print(f"Error in transform_publisher_urls: {str(e)}")
        # Return original URL if transformation fails
        return [url] if url else []
    
    return transformed_urls

def sanitize_url(url):
    """Clean and validate a URL"""
    if not url:
        return None
        
    # Remove any whitespace
    url = url.strip()
    
    # Split on commas if present and take the first valid URL
    if ',' in url:
        urls = [u.strip() for u in url.split(',')]
        # Take the first valid-looking URL
        for potential_url in urls:
            if potential_url.startswith('http'):
                return potential_url
        return urls[0]  # If no http URLs found, return first part
    
    return url

def get_unpaywall_pdf_url(data):
    """Extract PDF URL from Unpaywall data using multiple methods"""
    pdf_urls = set()  # Use set to avoid duplicates
    
    # Try best_oa_location first
    best_location = data.get("best_oa_location", {})
    if best_location:
        # Direct PDF URL
        pdf_url = best_location.get("url_for_pdf")
        if pdf_url:
            # Split in case we get concatenated URLs
            for url in pdf_url.split(','):
                url = url.strip()
                if url:
                    pdf_urls.add(url)
            
        # Try the main URL
        url = best_location.get("url")
        if url:
            for u in url.split(','):
                u = u.strip()
                if u:
                    pdf_urls.add(u)
    
    # Get all locations
    all_locations = data.get("oa_locations", [])
    for location in all_locations:
        # Try PDF URL first
        pdf_url = location.get("url_for_pdf")
        if pdf_url:
            for url in pdf_url.split(','):
                url = url.strip()
                if url:
                    pdf_urls.add(url)
            
        # Try main URL
        url = location.get("url")
        if url:
            for u in url.split(','):
                u = u.strip()
                if u:
                    pdf_urls.add(u)
    
    # Remove any None values or empty strings
    pdf_urls = {url for url in pdf_urls if url}
    
    # Debug logging
    if pdf_urls:
        print("\nFound PDF URLs:")
        for url in pdf_urls:
            print(f"- {url}")
    
    return list(pdf_urls)

def try_download_url(url, headers, filepath, max_retries=3, timeout=30, chunk_size=8192):
    """Try to download from a specific URL"""
    if not url:
        print("No URL provided")
        return False
        
    # Add PDF-specific headers
    pdf_headers = headers.copy()
    pdf_headers.update({
        'Accept': 'application/pdf,application/x-pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    
    for attempt in range(max_retries):
        try:
            print(f"\nDownload attempt {attempt + 1}/{max_retries} for URL: {url}")
            print("Using headers:", pdf_headers)
            
            # Make initial request with stream=True to check headers
            response = requests.get(url, headers=pdf_headers, timeout=timeout, stream=True, allow_redirects=True)
            print(f"Response status: {response.status_code}")
            print(f"Response URL after redirects: {response.url}")
            
            # Print all response headers for debugging
            print("\nResponse headers:")
            for header, value in response.headers.items():
                print(f"{header}: {value}")
            
            # Get content type and disposition
            content_type = response.headers.get('content-type', '').lower()
            content_disposition = response.headers.get('content-disposition', '').lower()
            
            # Check if it's a direct download (either PDF content type or attachment disposition)
            is_pdf = ('pdf' in content_type)
            is_download = ('attachment' in content_disposition) or ('filename' in content_disposition)
            
            print(f"\nContent checks:")
            print(f"Is PDF by content-type: {is_pdf}")
            print(f"Is download by disposition: {is_download}")
            
            if response.status_code == 200 and (is_pdf or is_download):
                # Stream the download
                total_size = 0
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            total_size += len(chunk)
                            f.write(chunk)
                            
                print(f"Download completed. Total size: {total_size} bytes")
                
                if total_size > 1024:  # Minimum size check (1KB)
                    # Verify it's a PDF
                    try:
                        with open(filepath, 'rb') as f:
                            header = f.read(4)
                            if header.startswith(b'%PDF'):
                                print("File verified as PDF")
                                return True
                            else:
                                print("File does not appear to be a PDF")
                                os.remove(filepath)
                    except Exception as e:
                        print(f"Error verifying PDF: {str(e)}")
                        if os.path.exists(filepath):
                            os.remove(filepath)
                else:
                    print(f"Downloaded file too small ({total_size} bytes), might be invalid")
                    if os.path.exists(filepath):
                        os.remove(filepath)
            else:
                print("Not a direct download - checking for PDF links in HTML")
                
                # Try to find PDF link in HTML response
                if 'html' in content_type:
                    try:
                        html_content = response.text.lower()
                        pdf_links = []
                        
                        # Look for common PDF link patterns
                        pdf_patterns = [
                            r'href=[\'"]([^\'"]+\.pdf)[\'"]',
                            r'content=[\'"]([^\'"]+\.pdf)[\'"]',
                            r'data-pdf-url=[\'"]([^\'"]+)[\'"]',
                            r'citation_pdf_url[\'"][^\'"]*[\'"]([^\'"]+)[\'"]'
                        ]
                        
                        for pattern in pdf_patterns:
                            matches = re.findall(pattern, html_content)
                            pdf_links.extend(matches)
                        
                        if pdf_links:
                            print(f"Found {len(pdf_links)} potential PDF links in HTML")
                            for pdf_link in pdf_links:
                                if not pdf_link.startswith('http'):
                                    # Convert relative URL to absolute
                                    from urllib.parse import urljoin
                                    pdf_link = urljoin(url, pdf_link)
                                
                                print(f"Trying extracted PDF link: {pdf_link}")
                                # Recursively try the PDF link with fewer retries
                                if try_download_url(pdf_link, headers, filepath, max_retries=1):
                                    return True
                    except Exception as e:
                        print(f"Error parsing HTML response: {str(e)}")
                        
        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                print("Retrying...")
                continue
        except requests.exceptions.RequestException as e:
            print(f"Request error on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                print("Retrying...")
                continue
        except Exception as e:
            print(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                print("Retrying...")
                continue
    
    print("All download attempts failed")
    return False

def download_pdf(paper, temp_dir):
    """Try to download PDF from various sources"""
    if not paper.get('doi'):
        print(f"No DOI available for paper: {paper['title']}")
        return None
        
    filename = sanitize_filename(f"{paper['year']}_{paper['title'][:100]}.pdf")
    filepath = os.path.join(temp_dir, filename)
    
    print(f"\nAttempting to download: {paper['title']}")
    print(f"DOI: {paper['doi']}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/pdf,*/*',
    }
    
    # Try Unpaywall first if available
    if "unpaywall" in paper['availability']['sources']:
        try:
            print(f"\nTrying Unpaywall download...")
            # Get fresh Unpaywall data
            unpaywall_url = f"{UNPAYWALL_API}{paper['doi']}?email={UNPAYWALL_EMAIL}"
            unpaywall_res = requests.get(unpaywall_url, timeout=10)
            
            if unpaywall_res.status_code == 200:
                data = unpaywall_res.json()
                
                # Get best_oa_location URL
                best_location = data.get('best_oa_location', {})
                if best_location:
                    pdf_url = best_location.get('url_for_pdf')
                    if pdf_url:
                        # Try each URL from the comma-separated list
                        urls = [u.strip() for u in pdf_url.split(',')]
                        print(f"\nFound {len(urls)} URLs to try:")
                        for url in urls:
                            print(f"\nTrying URL: {url}")
                            try:
                                response = requests.get(url, headers=headers, stream=True)
                                if response.status_code == 200:
                                    with open(filepath, 'wb') as f:
                                        for chunk in response.iter_content(chunk_size=8192):
                                            if chunk:
                                                f.write(chunk)
                                    print("Download successful!")
                                    return filename
                            except Exception as e:
                                print(f"Failed to download from {url}: {str(e)}")
                                continue
                                
                    # If PDF URL didn't work, try main URL
                    url = best_location.get('url')
                    if url:
                        urls = [u.strip() for u in url.split(',')]
                        for url in urls:
                            print(f"\nTrying URL: {url}")
                            try:
                                response = requests.get(url, headers=headers, stream=True)
                                if response.status_code == 200:
                                    with open(filepath, 'wb') as f:
                                        for chunk in response.iter_content(chunk_size=8192):
                                            if chunk:
                                                f.write(chunk)
                                    print("Download successful!")
                                    return filename
                            except Exception as e:
                                print(f"Failed to download from {url}: {str(e)}")
                                continue
                
                # Try all other locations
                locations = data.get('oa_locations', [])
                for location in locations:
                    pdf_url = location.get('url_for_pdf')
                    if pdf_url:
                        urls = [u.strip() for u in pdf_url.split(',')]
                        for url in urls:
                            print(f"\nTrying URL: {url}")
                            try:
                                response = requests.get(url, headers=headers, stream=True)
                                if response.status_code == 200:
                                    with open(filepath, 'wb') as f:
                                        for chunk in response.iter_content(chunk_size=8192):
                                            if chunk:
                                                f.write(chunk)
                                    print("Download successful!")
                                    return filename
                            except Exception as e:
                                print(f"Failed to download from {url}: {str(e)}")
                                continue
                    
                    url = location.get('url')
                    if url:
                        urls = [u.strip() for u in url.split(',')]
                        for url in urls:
                            print(f"\nTrying URL: {url}")
                            try:
                                response = requests.get(url, headers=headers, stream=True)
                                if response.status_code == 200:
                                    with open(filepath, 'wb') as f:
                                        for chunk in response.iter_content(chunk_size=8192):
                                            if chunk:
                                                f.write(chunk)
                                    print("Download successful!")
                                    return filename
                            except Exception as e:
                                print(f"Failed to download from {url}: {str(e)}")
                                continue
            else:
                print(f"Unpaywall API error: {unpaywall_res.status_code}")
        except Exception as e:
            print(f"Unpaywall process failed: {str(e)}")
    
    # Try direct DOI/publisher download if marked as available
    if "publisher" in paper['availability']['sources']:
        try:
            print(f"\nTrying publisher/DOI download...")
            doi_url = f"https://doi.org/{paper['doi']}"
            response = requests.get(doi_url, headers=headers, stream=True)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                print("Download successful!")
                return filename
        except Exception as e:
            print(f"Publisher download failed: {str(e)}")
    
    print("All download attempts failed")
    return None

def check_pdf_availability(doi):
    """Check if a PDF is actually downloadable from various sources"""
    if not doi:
        return {
            "is_available": False,
            "is_findable": False,
            "sources": []
        }
    
    available_sources = []
    
    # Try Unpaywall
    try:
        unpaywall_res = requests.get(
            f"{UNPAYWALL_API}{doi}?email={UNPAYWALL_EMAIL}",
            timeout=5
        )
        if unpaywall_res.status_code == 200:
            data = unpaywall_res.json()
            if data.get("is_oa"):
                # Check for actual PDF URLs
                pdf_urls = get_unpaywall_pdf_url(data)
                if pdf_urls:
                    available_sources.append("unpaywall")
    except Exception as e:
        print(f"Unpaywall check failed for {doi}: {str(e)}")
    
    # Try DOI resolution and check if it's a direct PDF
    try:
        doi_res = requests.head(f"https://doi.org/{doi}", timeout=5, allow_redirects=True)
        if doi_res.status_code == 200:
            content_type = doi_res.headers.get('content-type', '').lower()
            if 'pdf' in content_type:
                available_sources.append("publisher")
    except Exception as e:
        print(f"DOI check failed for {doi}: {str(e)}")
    
    # If we have no direct sources but have a DOI, mark as "findable" but not directly available
    is_findable = bool(doi)
    
    return {
        "is_available": len(available_sources) > 0,
        "is_findable": is_findable,
        "sources": available_sources
    }

# === Step 3: Get paper access links ===
@app.route("/download-pdfs", methods=["POST"])
@validate_request(["search_string"])
@handle_api_error
def download_pdfs():
    data = request.get_json()
    search_string = data["search_string"]
    page_size = 500  # Increased from 100 to 500
    
    print(f"\n=== Starting PDF Download Process ===")
    print(f"Using search string: {search_string}")
    
    try:
        # First get the list of PMIDs from PubMed
        search_params = {
            "db": "pubmed",
            "term": search_string,
            "retmode": "json",
            "retmax": page_size
        }
        
        print(f"Searching PubMed with params: {search_params}")
        search_res = requests.get(PUBMED_SEARCH_URL, params=search_params)
        search_res.raise_for_status()
        
        try:
            search_data = search_res.json()
        except Exception as e:
            print(f"Error parsing search response: {str(e)}")
            print(f"Response content: {search_res.text}")
            return jsonify({
                "error": "Failed to parse PubMed search response",
                "pdfs": [],
                "total_results": 0
            }), 500
        
        if "esearchresult" not in search_data:
            print(f"Unexpected PubMed response: {search_data}")
            return jsonify({"message": "Invalid response from PubMed", "pdfs": []}), 500
            
        pmids = search_data["esearchresult"].get("idlist", [])
        total_results = int(search_data["esearchresult"].get("count", 0))
        
        print(f"Found {total_results} total results")
        print(f"Retrieved {len(pmids)} PMIDs")
        
        if not pmids:
            return jsonify({
                "message": "No papers found",
                "pdfs": [],
                "total_results": 0
            }), 200
            
        # Now fetch details for these PMIDs
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml"
        }
        
        print(f"Fetching paper details from PubMed")
        fetch_res = requests.get(PUBMED_FETCH_URL, params=fetch_params)
        fetch_res.raise_for_status()
        
        # Parse XML response
        from xml.etree import ElementTree as ET
        try:
            root = ET.fromstring(fetch_res.content)
        except Exception as e:
            print(f"Error parsing XML response: {str(e)}")
            print(f"Response content: {fetch_res.text[:500]}...")
            return jsonify({
                "error": "Failed to parse PubMed paper details",
                "pdfs": [],
                "total_results": 0
            }), 500

        pdf_links = []
        for article in root.findall(".//PubmedArticle"):
            try:
                # Get PMID
                pmid = article.find(".//PMID").text
                
                # Get DOI if available
                doi = None
                article_ids = article.findall(".//ArticleId")
                for id_elem in article_ids:
                    if id_elem.get("IdType") == "doi":
                        doi = id_elem.text
                        break
                
                # Get article metadata
                article_elem = article.find(".//Article")
                if article_elem is None:
                    continue
                    
                title = article_elem.find(".//ArticleTitle")
                title = title.text if title is not None else "Untitled"
                
                abstract = article_elem.find(".//Abstract/AbstractText")
                abstract = abstract.text if abstract is not None else "No abstract available"
                
                journal = article_elem.find(".//Journal/Title")
                journal = journal.text if journal is not None else "Unknown Journal"
                
                year = article_elem.find(".//PubDate/Year")
                if year is None:
                    medline_date = article_elem.find(".//PubDate/MedlineDate")
                    year = medline_date.text[:4] if medline_date is not None else "Unknown Year"
                else:
                    year = year.text
                
                # Get authors
                authors = []
                author_list = article_elem.find(".//AuthorList")
                if author_list is not None:
                    for author in author_list.findall(".//Author"):
                        lastname = author.find("LastName")
                        firstname = author.find("ForeName")
                        if lastname is not None:
                            author_name = lastname.text
                            if firstname is not None:
                                author_name = f"{firstname.text} {lastname.text}"
                            authors.append(author_name)
                
                authors_str = ", ".join(authors) if authors else "Unknown Authors"
                
                # Check PDF availability
                availability = check_pdf_availability(doi)
                
                paper_info = {
                    "title": title,
                    "authors": authors_str,
                    "year": year,
                    "journal": journal,
                    "doi": doi,
                    "pmid": pmid,
                    "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "abstract": abstract,
                    "access_urls": {
                        "libkey": f"https://doi.org/{doi}" if doi else None,
                        "doi": f"https://doi.org/{doi}" if doi else None,
                        "unpaywall": None,
                        "scihub": f"https://sci-hub.se/{doi}" if doi else None
                    },
                    "availability": {
                        "is_available": availability["is_available"],
                        "is_findable": availability["is_findable"],
                        "sources": availability["sources"]
                    }
                }
                
                # Add Unpaywall URL if available
                if "unpaywall" in availability["sources"]:
                    try:
                        unpaywall_res = requests.get(
                            f"{UNPAYWALL_API}{doi}?email={UNPAYWALL_EMAIL}",
                            timeout=5
                        )
                        if unpaywall_res.status_code == 200:
                            data = unpaywall_res.json()
                            pdf_urls = get_unpaywall_pdf_url(data)
                            if pdf_urls:
                                paper_info["access_urls"]["unpaywall"] = pdf_urls
                    except Exception as e:
                        print(f"Error fetching Unpaywall data for DOI {doi}: {str(e)}")
                
                pdf_links.append(paper_info)
                
            except Exception as e:
                print(f"Error processing article {pmid if 'pmid' in locals() else 'unknown'}: {str(e)}")
                continue
        
        # Sort papers: Available first, then findable, then others, and by year within each group
        pdf_links.sort(key=lambda x: (
            not x["availability"]["is_available"],
            not x["availability"]["is_findable"],
            x["year"]
        ), reverse=True)
        
        print(f"\nSuccessfully processed {len(pdf_links)} papers")
        print(f"Directly downloadable papers: {len([p for p in pdf_links if p['availability']['is_available']])}")
        print(f"Findable but not directly downloadable: {len([p for p in pdf_links if p['availability']['is_findable'] and not p['availability']['is_available']])}")
        
        return jsonify({
            "pdfs": pdf_links,
            "total_results": total_results,
            "available_count": len([p for p in pdf_links if p["availability"]["is_available"]]),
            "findable_count": len([p for p in pdf_links if p["availability"]["is_findable"] and not p["availability"]["is_available"]])
        })
        
    except Exception as e:
        print(f"\nError in download_pdfs: {str(e)}")
        return jsonify({
            "error": f"Failed to process papers: {str(e)}",
            "pdfs": [],
            "total_results": 0
        }), 500

def sanitize_filename(filename):
    """Sanitize filename to be safe for all operating systems"""
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    # Limit length and remove trailing spaces/dots
    filename = filename[:200].strip('. ')
    return filename

# === Step 4: Bulk download papers ===
@app.route("/bulk-download", methods=["POST"])
@validate_request(["papers"])
@handle_api_error
def bulk_download():
    data = request.get_json()
    papers = data["papers"]
    
    print(f"\n=== Starting bulk download of {len(papers)} papers ===")
    
    # Create downloads directory if it doesn't exist
    downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
    os.makedirs(downloads_dir, exist_ok=True)
    
    # Create a new directory for this batch
    batch_dir = os.path.join(downloads_dir, f'batch_{int(time.time())}')
    os.makedirs(batch_dir, exist_ok=True)
    
    print(f"Created batch directory: {batch_dir}")
    
    try:
        # Create a manifest file with all paper details
        manifest_content = []
        for paper in papers:
            manifest_content.append(
                f"Title: {paper['title']}\n"
                f"Authors: {paper['authors']}\n"
                f"Year: {paper['year']}\n"
                f"Journal: {paper['journal']}\n"
                f"DOI: {paper.get('doi', 'N/A')}\n"
                f"PubMed URL: {paper.get('pubmed_url', 'N/A')}\n"
                f"Abstract: {paper.get('abstract', 'N/A')}\n"
                f"Access URLs:\n"
                f"  - DOI: {paper['access_urls'].get('doi', 'N/A')}\n"
                f"  - LibKey: {paper['access_urls'].get('libkey', 'N/A')}\n"
                f"  - Unpaywall: {paper['access_urls'].get('unpaywall', 'N/A')}\n"
                f"  - Sci-Hub: {paper['access_urls'].get('scihub', 'N/A')}\n"
                f"Availability:\n"
                f"  - Is Available: {paper['availability'].get('is_available', False)}\n"
                f"  - Sources: {', '.join(paper['availability'].get('sources', []))}\n"
                f"\n---\n\n"
            )
        
        manifest_path = os.path.join(batch_dir, "papers_manifest.txt")
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("".join(manifest_content))
        
        print(f"\nDownloading papers...")
        # Download PDFs in parallel with a smaller number of workers to avoid overwhelming servers
        successful_downloads = []
        failed_downloads = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_paper = {
                executor.submit(download_pdf, paper, batch_dir): paper 
                for paper in papers if paper['availability']['is_available']
            }
            
            for future in concurrent.futures.as_completed(future_to_paper):
                paper = future_to_paper[future]
                try:
                    filename = future.result()
                    if filename:
                        successful_downloads.append(filename)
                        print(f"Successfully downloaded: {paper['title']}")
                    else:
                        failed_downloads.append(paper['title'])
                        print(f"Failed to download: {paper['title']}")
                except Exception as e:
                    failed_downloads.append(paper['title'])
                    print(f"Error downloading {paper['title']}: {str(e)}")
        
        print(f"\nDownload summary:")
        print(f"Successfully downloaded: {len(successful_downloads)} papers")
        print(f"Failed to download: {len(failed_downloads)} papers")
        
        if not successful_downloads:
            raise Exception("No papers were successfully downloaded")
        
        # Create zip file
        zip_filename = f'papers_{int(time.time())}.zip'
        zip_path = os.path.join(downloads_dir, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add manifest
            zipf.write(manifest_path, "papers_manifest.txt")
            
            # Add downloaded PDFs
            for filename in successful_downloads:
                filepath = os.path.join(batch_dir, filename)
                if os.path.exists(filepath):
                    zipf.write(filepath, filename)
        
        # Clean up batch directory after creating zip
        import shutil
        shutil.rmtree(batch_dir)
        
        # Send the zip file
        try:
            response = send_file(
                zip_path,
                mimetype='application/zip',
                as_attachment=True,
                download_name='papers.zip'
            )
            
            # Delete the zip file after sending
            @response.call_on_close
            def cleanup():
                try:
                    os.remove(zip_path)
                except:
                    pass
                    
            return response
            
        except Exception as e:
            print(f"Error sending file: {str(e)}")
            if os.path.exists(zip_path):
                os.remove(zip_path)
            raise
            
    except Exception as e:
        print(f"Error in bulk_download: {str(e)}")
        # Clean up on error
        if os.path.exists(batch_dir):
            shutil.rmtree(batch_dir)
        if 'zip_path' in locals() and os.path.exists(zip_path):
            os.remove(zip_path)
        raise

if __name__ == '__main__':
    app.run(debug=True)
