import aiohttp
import asyncio
import socket
import ssl
import urllib.parse
from typing import Dict, List, Any
import dns.resolver
import whois
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class LinkAnalyzer:
    def __init__(self, config):
        self.config = config
        self.session = None
        self.known_phishing_domains = set()
        self.trusted_domains = {
            'google.com', 'github.com', 'microsoft.com', 'apple.com',
            'amazon.com', 'wikipedia.org', 'youtube.com', 'twitter.com',
            'facebook.com', 'instagram.com', 'linkedin.com', 'reddit.com'
        }
        
    async def initialize(self):
        """Initialize HTTP session and load blacklists"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10)
        )
        await self.load_blacklists()
        
    async def load_blacklists(self):
        """Load known phishing/malware domain lists"""
        # Load from various threat intelligence sources
        sources = [
            'https://raw.githubusercontent.com/mitchellkrogza/Phishing.Database/master/phishing-domains-ACTIVE.txt',
            'https://openphish.com/feed.txt'
        ]
        
        for source in sources:
            try:
                async with self.session.get(source) as response:
                    if response.status == 200:
                        content = await response.text()
                        domains = set(line.strip() for line in content.split('\n') if line.strip())
                        self.known_phishing_domains.update(domains)
            except Exception as e:
                logger.error(f"Failed to load blacklist from {source}: {e}")
                
    async def analyze(self, url: str) -> Dict[str, Any]:
        """Perform comprehensive link analysis"""
        if not self.session:
            await self.initialize()
            
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        
        analysis = {
            'url': url,
            'domain': domain,
            'threat_score': 0.0,
            'confidence': 0.0,
            'flags': [],
            'checks': {}
        }
        
        # Run all checks concurrently
        checks = await asyncio.gather(
            self.check_domain_reputation(domain),
            self.check_ssl_certificate(domain),
            self.check_domain_age(domain),
            self.check_url_shortener(url),
            self.check_suspicious_patterns(url),
            self.check_http_headers(url),
            return_exceptions=True
        )
        
        # Process results
        for check in checks:
            if isinstance(check, Exception):
                logger.error(f"Check failed: {check}")
                continue
            if check:
                analysis['checks'].update(check)
                analysis['threat_score'] += check.get('threat_contribution', 0)
                analysis['flags'].extend(check.get('flags', []))
                
        # Calculate confidence based on successful checks
        successful_checks = sum(1 for c in checks if not isinstance(c, Exception))
        analysis['confidence'] = successful_checks / len(checks)
        
        # Normalize threat score
        analysis['threat_score'] = min(1.0, analysis['threat_score'])
        
        return analysis
        
    async def check_domain_reputation(self, domain: str) -> Dict[str, Any]:
        """Check domain against known blacklists"""
        result = {
            'domain_reputation': {},
            'threat_contribution': 0,
            'flags': []
        }
        
        # Check if domain is in known phishing list
        if domain in self.known_phishing_domains:
            result['domain_reputation']['blacklisted'] = True
            result['threat_contribution'] = 0.8
            result['flags'].append('Domain is blacklisted')
            
        # Check if domain is trusted
        elif any(trusted in domain for trusted in self.trusted_domains):
            result['domain_reputation']['trusted'] = True
            result['threat_contribution'] = -0.3
            
        # Check for domain spoofing
        if self.check_homograph_attack(domain):
            result['threat_contribution'] += 0.5
            result['flags'].append('Possible homograph attack detected')
            
        return result
        
    async def check_ssl_certificate(self, domain: str) -> Dict[str, Any]:
        """Check SSL certificate validity"""
        result = {
            'ssl_check': {},
            'threat_contribution': 0,
            'flags': []
        }
        
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Check certificate validity
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    if not_after < datetime.now():
                        result['ssl_check']['expired'] = True
                        result['threat_contribution'] = 0.3
                        result['flags'].append('SSL certificate expired')
                    else:
                        result['ssl_check']['valid'] = True
                        
        except Exception as e:
            result['ssl_check']['error'] = str(e)
            result['threat_contribution'] = 0.2
            result['flags'].append('SSL certificate check failed')
            
        return result
        
    async def check_domain_age(self, domain: str) -> Dict[str, Any]:
        """Check domain registration age"""
        result = {
            'domain_age': {},
            'threat_contribution': 0,
            'flags': []
        }
        
        try:
            w = whois.whois(domain)
            if w.creation_date:
                creation_date = w.creation_date
                if isinstance(creation_date, list):
                    creation_date = creation_date[0]
                    
                age_days = (datetime.now() - creation_date).days
                result['domain_age']['days'] = age_days
                
                if age_days < 30:
                    result['threat_contribution'] = 0.4
                    result['flags'].append(f'Domain is very new ({age_days} days)')
                elif age_days < 90:
                    result['threat_contribution'] = 0.2
                    result['flags'].append(f'Domain is relatively new ({age_days} days)')
                    
        except Exception as e:
            logger.error(f"Domain age check failed: {e}")
            
        return result
        
    async def check_url_shortener(self, url: str) -> Dict[str, Any]:
        """Check if URL uses shortener service"""
        result = {
            'url_shortener': {},
            'threat_contribution': 0,
            'flags': []
        }
        
        shorteners = [
            'bit.ly', 'tinyurl.com', 'goo.gl', 'ow.ly', 't.co',
            'short.link', 'tiny.cc', 'is.gd', 'soo.gd', 'rb.gy'
        ]
        
        parsed = urllib.parse.urlparse(url)
        if any(shortener in parsed.netloc for shortener in shorteners):
            result['url_shortener']['detected'] = True
            result['threat_contribution'] = 0.3
            result['flags'].append('URL shortener detected')
            
            # Try to resolve the actual URL
            try:
                async with self.session.head(url, allow_redirects=True) as response:
                    final_url = str(response.url)
                    result['url_shortener']['resolved'] = final_url
            except:
                pass
                
        return result
        
    async def check_suspicious_patterns(self, url: str) -> Dict[str, Any]:
        """Check for suspicious URL patterns"""
        result = {
            'pattern_check': {},
            'threat_contribution': 0,
            'flags': []
        }
        
        suspicious_patterns = [
            (r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', 'IP address instead of domain'),
            (r'@', 'URL contains @ symbol'),
            (r'[^\x00-\x7F]+', 'Non-ASCII characters in URL'),
            (r'(paypal|amazon|google|microsoft|apple|bank)(?!\.com)', 'Possible brand spoofing'),
            (r'\.tk$|\.ml$|\.ga$|\.cf$', 'Free domain TLD often used in scams'),
            (r'-{2,}', 'Multiple consecutive hyphens'),
            (r'\.(zip|rar|exe|scr|bat|cmd|com|pif|vbs|js)$', 'Executable file extension')
        ]
        
        import re
        for pattern, description in suspicious_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                result['pattern_check'][description] = True
                result['threat_contribution'] += 0.2
                result['flags'].append(description)
                
        return result
        
    async def check_http_headers(self, url: str) -> Dict[str, Any]:
        """Check HTTP response headers for suspicious indicators"""
        result = {
            'http_headers': {},
            'threat_contribution': 0,
            'flags': []
        }
        
        try:
            async with self.session.get(url, allow_redirects=False) as response:
                headers = response.headers
                
                # Check for suspicious redirects
                if response.status in [301, 302, 303, 307, 308]:
                    location = headers.get('Location', '')
                    if location and not location.startswith('https'):
                        result['threat_contribution'] += 0.2
                        result['flags'].append('Redirect to non-HTTPS URL')
                        
                # Check security headers
                security_headers = [
                    'X-Frame-Options',
                    'X-Content-Type-Options',
                    'Content-Security-Policy'
                ]
                
                missing_headers = [h for h in security_headers if h not in headers]
                if len(missing_headers) > 2:
                    result['threat_contribution'] += 0.1
                    result['flags'].append('Missing security headers')
                    
        except Exception as e:
            logger.error(f"HTTP headers check failed: {e}")
            
        return result
        
    def check_homograph_attack(self, domain: str) -> bool:
        """Check for homograph attacks using similar-looking characters"""
        homographs = {
            'a': ['а', 'ɑ', '@'],
            'e': ['е', 'ё', '3'],
            'o': ['о', '0', 'ο'],
            'i': ['і', 'l', '1'],
            'c': ['с', 'ϲ'],
            'p': ['р', 'ρ'],
            'x': ['х', '×'],
            'y': ['у', 'ү'],
            'n': ['п', 'ո']
        }
        
        for char, similars in homographs.items():
            if any(s in domain for s in similars):
                return True
        return False
