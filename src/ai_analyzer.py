import aiohttp
import asyncio
import logging
from typing import Dict, Any, List
import json
import os
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

class AIAnalyzer:
    def __init__(self, config):
        self.config = config
        self.ai_provider = config.get('ai.provider', 'openai')
        self.api_key = config.get(f'ai.{self.ai_provider}_api_key')
        self.model = config.get('ai.model', 'gpt-4')
        self.session = None
        
    async def initialize(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def analyze(self, url: str, basic_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to analyze the URL and its content"""
        if not self.session:
            await self.initialize()
            
        result = {
            'threat_score': 0.0,
            'confidence': 0.0,
            'flags': [],
            'ai_assessment': {}
        }
        
        # Fetch and analyze page content
        page_content = await self.fetch_page_content(url)
        
        if page_content:
            # Analyze with AI
            ai_response = await self.ai_content_analysis(url, page_content, basic_analysis)
            result.update(ai_response)
            
        # Search for reviews and complaints
        search_results = await self.search_web_reputation(url)
        if search_results:
            reputation_analysis = await self.ai_reputation_analysis(url, search_results)
            result['reputation'] = reputation_analysis
            
            # Update threat score based on reputation
            if reputation_analysis.get('has_complaints', False):
                result['threat_score'] += 0.4
                result['flags'].append('Negative reviews/complaints found')
                
        return result
        
    async def fetch_page_content(self, url: str) -> Dict[str, Any]:
        """Fetch and parse webpage content"""
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract relevant content
                    content = {
                        'title': soup.title.string if soup.title else '',
                        'meta_description': '',
                        'text': ' '.join(soup.stripped_strings)[:5000],  # Limit text
                        'forms': len(soup.find_all('form')),
                        'input_fields': len(soup.find_all('input')),
                        'scripts': len(soup.find_all('script')),
                        'external_links': []
                    }
                    
                    # Get meta description
                    meta_desc = soup.find('meta', attrs={'name': 'description'})
                    if meta_desc:
                        content['meta_description'] = meta_desc.get('content', '')
                        
                    # Get external links
                    for link in soup.find_all('a', href=True)[:20]:
                        href = link['href']
                        if href.startswith('http'):
                            content['external_links'].append(href)
                            
                    return content
                    
        except Exception as e:
            logger.error(f"Failed to fetch page content: {e}")
            
        return None
        
    async def ai_content_analysis(
        self, 
        url: str, 
        content: Dict[str, Any], 
        basic_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze content using AI"""
        
        prompt = f"""
        Analyze the following webpage for potential scam or phishing indicators.
        
        URL: {url}
        Title: {content.get('title', 'N/A')}
        Description: {content.get('meta_description', 'N/A')}
        Number of forms: {content.get('forms', 0)}
        Number of input fields: {content.get('input_fields', 0)}
        
        Basic security analysis:
        {json.dumps(basic_analysis, indent=2)}
        
        Page content excerpt:
        {content.get('text', '')[:1000]}
        
        Please analyze for:
        1. Phishing indicators (fake login pages, credential harvesting)
        2. Scam patterns (too good to be true offers, urgency tactics)
        3. Malware distribution signs
        4. Legitimate business indicators
        
        Respond in JSON format with:
        {{
            "is_suspicious": boolean,
            "threat_level": "low|medium|high",
            "confidence": float (0-1),
            "indicators": [list of specific suspicious indicators found],
            "legitimate_signs": [list of legitimate business indicators],
            "recommendation": "safe|caution|suspicious|danger"
        }}
        """
        
        try:
            if self.ai_provider == 'openai':
                response = await self.call_openai(prompt)
            elif self.ai_provider == 'anthropic':
                response = await self.call_anthropic(prompt)
            else:
                response = await self.call_local_llm(prompt)
                
            # Parse AI response
            ai_result = json.loads(response)
            
            result = {
                'threat_score': 0.0,
                'confidence': ai_result.get('confidence', 0.5),
                'flags': ai_result.get('indicators', []),
                'ai_assessment': ai_result
            }
            
            # Calculate threat score
            if ai_result.get('threat_level') == 'high':
                result['threat_score'] = 0.8
            elif ai_result.get('threat_level') == 'medium':
                result['threat_score'] = 0.5
            elif ai_result.get('threat_level') == 'low':
                result['threat_score'] = 0.2
                
            return result
            
        except Exception as e:
            logger.error(f"AI content analysis failed: {e}")
            return {
                'threat_score': 0.0,
                'confidence': 0.0,
                'flags': ['AI analysis unavailable'],
                'ai_assessment': {}
            }
            
    async def search_web_reputation(self, url: str) -> List[Dict[str, Any]]:
        """Search for reviews and complaints about the URL"""
        domain = urllib.parse.urlparse(url).netloc
        
        search_queries = [
            f'"{domain}" scam OR fraud OR complaint',
            f'"{domain}" review OR experience',
            f'is "{domain}" legitimate OR safe'
        ]
        
        results = []
        
        for query in search_queries:
            try:
                # Use a web search API (you can use SerpAPI, Google Custom Search, etc.)
                search_results = await self.web_search(query)
                results.extend(search_results)
            except Exception as e:
                logger.error(f"Web search failed: {e}")
                
        return results[:10]  # Limit to top 10 results
        
    async def ai_reputation_analysis(
        self, 
        url: str, 
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze web reputation using AI"""
        
        results_summary = "\n".join([
            f"- {r.get('title', '')}: {r.get('snippet', '')}"
            for r in search_results
        ])
        
        prompt = f"""
        Analyze the following search results about {url} to determine its reputation:
        
        Search Results:
        {results_summary}
        
        Please determine:
        1. Are there legitimate complaints about this site?
        2. What is the overall sentiment (positive/negative/mixed)?
        3. Are there scam reports?
        4. Is this a known legitimate business?
        
        Respond in JSON format with:
        {{
            "has_complaints": boolean,
            "complaint_severity": "none|low|medium|high",
            "sentiment": "positive|negative|mixed|unknown",
            "scam_reports": boolean,
            "is_legitimate_business": boolean,
            "summary": "brief summary of findings"
        }}
        """
        
        try:
            if self.ai_provider == 'openai':
                response = await self.call_openai(prompt)
            else:
                response = await self.call_local_llm(prompt)
                
            return json.loads(response)
            
        except Exception as e:
            logger.error(f"AI reputation analysis failed: {e}")
            return {}
            
    async def call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': 'You are a security expert analyzing URLs for potential threats.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.3,
            'response_format': {'type': 'json_object'}
        }
        
        async with self.session.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data
        ) as response:
            result = await response.json()
            return result['choices'][0]['message']['content']
            
    async def call_anthropic(self, prompt: str) -> str:
        """Call Anthropic Claude API"""
        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        data = {
            'model': 'claude-3-opus-20240229',
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': 1000
        }
        
        async with self.session.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data
        ) as response:
            result = await response.json()
            return result['content'][0]['text']
            
    async def call_local_llm(self, prompt: str) -> str:
        """Call local LLM (Ollama, LlamaCpp, etc.)"""
        # Example for Ollama
        data = {
            'model': self.config.get('ai.local_model', 'llama2'),
            'prompt': prompt,
            'stream': False,
            'format': 'json'
        }
        
        async with self.session.post(
            'http://localhost:11434/api/generate',
            json=data
        ) as response:
            result = await response.json()
            return result['response']
            
    async def web_search(self, query: str) -> List[Dict[str, Any]]:
        """Perform web search (implement with your preferred search API)"""
        # Example using SerpAPI
        params = {
            'q': query,
            'api_key': self.config.get('search.api_key'),
            'num': 5
        }
        
        async with self.session.get(
            'https://serpapi.com/search',
            params=params
        ) as response:
            data = await response.json()
            return data.get('organic_results', [])
