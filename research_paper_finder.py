import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import json
import time
from datetime import datetime
import warnings
import re
from difflib import SequenceMatcher

# Filter out the XML parsing warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

class ResearchPaperFinder:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.results = []
        
    def format_authors(self, authors):
        """Helper function to format author information"""
        if not authors:
            return "No authors listed"
        if isinstance(authors, list):
            if isinstance(authors[0], dict):
                # Handle PubMed author format
                return ', '.join(author.get('name', '') for author in authors)
            return ', '.join(authors)
        return str(authors)

    def is_relevant_to_cervical_cancer(self, text):
        """Check if the paper is related to cervical cancer and colposcopy"""
        relevant_terms = [
            'cervical cancer', 'cervix', 'cervical', 'colposcopy', 'pap smear',
            'hpv', 'human papillomavirus', 'cin', 'cervical intraepithelial neoplasia',
            'precancerous lesions', 'cervical screening', 'who colposcopy', 'iarc colposcopy'
        ]
        
        text_lower = text.lower()
        return any(term in text_lower for term in relevant_terms)

    def calculate_similarity(self, title1, title2):
        """Calculate similarity between two titles using sequence matcher"""
        return SequenceMatcher(None, title1.lower(), title2.lower()).ratio()

    def extract_links_google_scholar(self, result):
        """Extract paper links from Google Scholar results"""
        links = {}
        
        # Look for direct PDF links
        pdf_link = result.select_one('.gs_or_ggsm a[href*=".pdf"]')
        if pdf_link and 'href' in pdf_link.attrs:
            links['pdf'] = pdf_link['href']
            
        # Look for main paper link
        title_link = result.select_one('.gs_rt a')
        if title_link and 'href' in title_link.attrs:
            links['main'] = title_link['href']
            
        # Look for citations link
        cite_link = result.select_one('a:contains("Cited by")')
        if cite_link and 'href' in cite_link.attrs:
            links['citations'] = f"https://scholar.google.com{cite_link['href']}"
            
        return links

    def search_google_scholar(self, query, num_pages=2):
        """Search Google Scholar for research papers"""
        print(f"\nSearching Google Scholar for: {query}")
        base_url = "https://scholar.google.com/scholar"
        papers = []
        
        for page in range(num_pages):
            try:
                print(f"  Page {page + 1}...")
                params = {
                    'q': query,
                    'start': page * 10
                }
                response = requests.get(base_url, params=params, headers=self.headers)
                soup = BeautifulSoup(response.text, 'lxml')
                
                for result in soup.select('.gs_ri'):
                    title_elem = result.select_one('.gs_rt')
                    if not title_elem:
                        continue
                    
                    title = title_elem.text.strip()
                    authors_venue = result.select_one('.gs_a').text if result.select_one('.gs_a') else "No author info"
                    snippet = result.select_one('.gs_rs').text if result.select_one('.gs_rs') else "No snippet"
                    
                    # Only include papers relevant to cervical cancer
                    if self.is_relevant_to_cervical_cancer(title) or self.is_relevant_to_cervical_cancer(snippet):
                        # Extract links
                        links = self.extract_links_google_scholar(result)
                        
                        paper = {
                            'title': title,
                            'authors_venue': authors_venue,
                            'snippet': snippet,
                            'source': 'Google Scholar',
                            'relevance_score': self.calculate_relevance_score(title, snippet),
                            'links': links
                        }
                        papers.append(paper)
                    
                time.sleep(2)
                
            except Exception as e:
                print(f"  Error on page {page + 1}: {str(e)}")
                
        print(f"Found {len(papers)} relevant papers from Google Scholar")
        return papers

    def calculate_relevance_score(self, title, abstract):
        """Calculate a relevance score based on keyword matching"""
        text = (title + " " + abstract).lower()
        
        # Define keywords with weights
        keywords = {
            'iarc colposcopy database': 5,
            'who colposcopy': 5,
            'iarcimagebankolpo': 5,
            'colposcopy image': 4,
            'cervical cancer': 3,
            'colposcopy': 3,
            'cervical': 2,
            'hpv': 2,
            'screening': 1,
            'dataset': 1
        }
        
        score = 0
        for keyword, weight in keywords.items():
            count = len(re.findall(r'\b' + re.escape(keyword) + r'\b', text))
            score += count * weight
            
        return score

    def search_pubmed(self, query):
        """Search PubMed for research papers"""
        print(f"\nSearching PubMed for: {query}")
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        papers = []
        
        try:
            params = {
                'db': 'pubmed',
                'term': query,
                'retmode': 'json',
                'retmax': 20
            }
            response = requests.get(base_url, params=params)
            data = response.json()
            
            if 'esearchresult' in data and 'idlist' in data['esearchresult']:
                for pmid in data['esearchresult']['idlist']:
                    try:
                        details_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                        params = {
                            'db': 'pubmed',
                            'id': pmid,
                            'retmode': 'json'
                        }
                        details = requests.get(details_url, params=params).json()
                        
                        if 'result' in details and pmid in details['result']:
                            paper_details = details['result'][pmid]
                            title = paper_details.get('title', '')
                            summary = paper_details.get('summary', '')
                            
                            # Only include papers relevant to cervical cancer
                            if self.is_relevant_to_cervical_cancer(title) or self.is_relevant_to_cervical_cancer(summary):
                                paper = {
                                    'title': title,
                                    'authors': paper_details.get('authors', []),
                                    'pubdate': paper_details.get('pubdate', ''),
                                    'summary': summary,
                                    'source': 'PubMed',
                                    'pmid': pmid,
                                    'relevance_score': self.calculate_relevance_score(title, summary),
                                    'links': {
                                        'pubmed': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                                        'fulltext': f"https://www.ncbi.nlm.nih.gov/pmc/articles/pmid/{pmid}/"
                                    }
                                }
                                papers.append(paper)
                            
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"  Error fetching details for PMID {pmid}: {str(e)}")
                        
        except Exception as e:
            print(f"  Error searching PubMed: {str(e)}")
            
        print(f"Found {len(papers)} relevant papers from PubMed")
        return papers

    def search_arxiv(self, query):
        """Search arXiv for research papers"""
        print(f"\nSearching arXiv for: {query}")
        base_url = "http://export.arxiv.org/api/query"
        papers = []
        
        try:
            params = {
                'search_query': query,
                'start': 0,
                'max_results': 20
            }
            response = requests.get(base_url, params=params)
            soup = BeautifulSoup(response.text, features='lxml-xml')
            
            for entry in soup.find_all('entry'):
                title = entry.title.text if entry.title else "No title"
                summary = entry.summary.text if entry.summary else "No summary"
                
                # Extract links
                links = {}
                for link in entry.find_all('link'):
                    if 'title' in link.attrs:
                        if link['title'] == 'pdf':
                            links['pdf'] = link['href']
                        elif link['title'] == 'doi':
                            links['doi'] = link['href']
                    elif link.get('rel') == 'alternate':
                        links['main'] = link['href']
                
                # Only include papers relevant to cervical cancer
                if self.is_relevant_to_cervical_cancer(title) or self.is_relevant_to_cervical_cancer(summary):
                    paper = {
                        'title': title,
                        'authors': [author.text for author in entry.find_all('author')],
                        'published': entry.published.text if entry.published else "No date",
                        'summary': summary,
                        'source': 'arXiv',
                        'relevance_score': self.calculate_relevance_score(title, summary),
                        'links': links
                    }
                    papers.append(paper)
                
        except Exception as e:
            print(f"  Error searching arXiv: {str(e)}")
            
        print(f"Found {len(papers)} relevant papers from arXiv")
        return papers

    def detect_duplicates(self, results):
        """Detect and remove duplicate papers using title similarity"""
        print("\nDetecting duplicate papers...")
        # First pass: Exact title matches
        unique_by_title = {}
        for paper in results:
            title = paper['title'].lower().strip()
            if title in unique_by_title:
                # Merge links if possible
                if 'links' in paper and 'links' in unique_by_title[title]:
                    unique_by_title[title]['links'].update(paper.get('links', {}))
                # Keep the entry with the higher relevance score
                if paper.get('relevance_score', 0) > unique_by_title[title].get('relevance_score', 0):
                    unique_by_title[title] = paper
            else:
                unique_by_title[title] = paper
        
        # Second pass: Fuzzy title matches
        fuzzy_unique = []
        processed_indices = set()
        
        titles = list(unique_by_title.values())
        for i in range(len(titles)):
            if i in processed_indices:
                continue
                
            paper1 = titles[i]
            duplicates = [paper1]
            processed_indices.add(i)
            
            for j in range(i+1, len(titles)):
                if j in processed_indices:
                    continue
                    
                paper2 = titles[j]
                similarity = self.calculate_similarity(paper1['title'], paper2['title'])
                
                if similarity > 0.85:  # Threshold for considering as duplicate
                    duplicates.append(paper2)
                    processed_indices.add(j)
            
            # Merge duplicates and keep the one with highest score
            if len(duplicates) > 1:
                print(f"  Found {len(duplicates)} similar papers: '{paper1['title'][:50]}...'")
                best_paper = max(duplicates, key=lambda x: x.get('relevance_score', 0))
                
                # Merge links from all duplicates
                all_links = {}
                for dup in duplicates:
                    if 'links' in dup:
                        all_links.update(dup.get('links', {}))
                
                if all_links:
                    best_paper['links'] = all_links
                    
                # Note that we found duplicates
                best_paper['duplicate_count'] = len(duplicates)
                fuzzy_unique.append(best_paper)
            else:
                fuzzy_unique.append(paper1)
        
        print(f"After duplicate detection: {len(results)} papers → {len(fuzzy_unique)} unique papers")
        return fuzzy_unique

    def search_all_sources(self, dataset_name):
        """Search all available sources for papers related to the dataset"""
        # More specific queries focused on cervical cancer and the dataset
        queries = [
            f"{dataset_name} cervical cancer colposcopy",
            "IARC colposcopy database cervical cancer",
            "WHO colposcopy images cervical cancer dataset",
            "colposcopy imaging cervical cancer screening",
            "cervical intraepithelial neoplasia colposcopy WHO"
        ]
        
        all_results = []
        for query in queries:
            print(f"\nSearching for: {query}")
            all_results.extend(self.search_google_scholar(query))
            all_results.extend(self.search_pubmed(query))
            all_results.extend(self.search_arxiv(query))
        
        # Detect and remove duplicates with sophisticated methods
        unique_results = self.detect_duplicates(all_results)
        
        # Sort by relevance score
        unique_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        self.results = unique_results
        return unique_results

    def save_results(self, filename=None):
        """Save search results to a JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'cervical_cancer_papers_{timestamp}.json'
            
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
            
        print(f"\nResults saved to {filename}")

def format_links(links):
    """Format links dictionary into a readable string"""
    if not links:
        return "No links available"
        
    formatted = []
    link_labels = {
        'main': 'Paper URL',
        'pdf': 'PDF Download',
        'pubmed': 'PubMed Page',
        'fulltext': 'Full Text',
        'doi': 'DOI Link',
        'citations': 'Citations'
    }
    
    for key, url in links.items():
        label = link_labels.get(key, key.capitalize())
        formatted.append(f"{label}: {url}")
        
    return "\n      ".join(formatted)

def main():
    finder = ResearchPaperFinder()
    dataset_name = "IARCImageBankColpo"
    
    print(f"Searching for cervical cancer papers using {dataset_name}...")
    results = finder.search_all_sources(dataset_name)
    
    print(f"\nFound {len(results)} relevant cervical cancer papers (sorted by relevance):")
    for i, paper in enumerate(results, 1):
        print(f"\n{i}. {paper['title']}")
        print(f"   Source: {paper['source']}")
        print(f"   Relevance Score: {paper.get('relevance_score', 'N/A')}")
        
        # Duplicate info
        if 'duplicate_count' in paper and paper['duplicate_count'] > 1:
            print(f"   Note: Combined {paper['duplicate_count']} duplicate/similar entries")
        
        # Handle different author formats
        if 'authors' in paper:
            authors = finder.format_authors(paper['authors'])
            print(f"   Authors: {authors}")
        elif 'authors_venue' in paper:
            print(f"   Authors/Venue: {paper['authors_venue']}")
            
        if 'published' in paper:
            print(f"   Published: {paper['published']}")
        elif 'pubdate' in paper:
            print(f"   Published: {paper['pubdate']}")
            
        if 'snippet' in paper:
            print(f"   Summary: {paper['snippet'][:200]}...")
        elif 'summary' in paper:
            print(f"   Summary: {paper['summary'][:200]}...")
            
        # Display links
        if 'links' in paper and paper['links']:
            print(f"   Links:\n      {format_links(paper['links'])}")
            
    # Save results
    finder.save_results()

if __name__ == "__main__":
    main()