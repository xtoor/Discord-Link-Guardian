#!/usr/bin/env python3
"""
Health check script for Discord Link Guardian Bot
Returns 0 if healthy, 1 if unhealthy
"""

import asyncio
import sys
import os
import aiohttp
import discord
from datetime import datetime
import psutil
import sqlite3

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config

class HealthChecker:
    def __init__(self):
        self.config = Config()
        self.checks = []
        self.warnings = []
        self.errors = []
        
    async def check_discord_connection(self):
        """Check Discord API connectivity"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://discord.com/api/v10') as resp:
                    if resp.status == 404:  # Expected for base endpoint
                        self.checks.append("✓ Discord API accessible")
                        return True
        except Exception as e:
            self.errors.append(f"✗ Discord API check failed: {e}")
            return False
            
    async def check_ai_provider(self):
        """Check AI provider connectivity"""
        provider = self.config.get('ai.provider')
        
        if provider == 'openai':
            url = 'https://api.openai.com/v1/models'
            headers = {'Authorization': f"Bearer {self.config.get('ai.openai_api_key')}"}
        elif provider == 'anthropic':
            url = 'https://api.anthropic.com/v1/messages'
            headers = {'x-api-key': self.config.get('ai.anthropic_api_key')}
        elif provider == 'local':
            url = f"http://localhost:11434/api/tags"
            headers = {}
        else:
            self.warnings.append("⚠ No AI provider configured")
            return True
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status in [200, 401, 403]:  # API is reachable
                        self.checks.append(f"✓ {provider.title()} AI provider accessible")
                        return True
        except Exception as e:
            self.warnings.append(f"⚠ {provider.title()} AI provider unreachable: {e}")
            return False
            
    def check_database(self):
        """Check database accessibility"""
        db_path = self.config.get('database.path', 'data/bot.db')
        
        try:
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                conn.close()
                self.checks.append(f"✓ Database accessible ({table_count} tables)")
                return True
            else:
                self.warnings.append(f"⚠ Database not found at {db_path}")
                return False
        except Exception as e:
            self.errors.append(f"✗ Database check failed: {e}")
            return False
            
    def check_system_resources(self):
        """Check system resource availability"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                self.warnings.append(f"⚠ High CPU usage: {cpu_percent}%")
            else:
                self.checks.append(f"✓ CPU usage: {cpu_percent}%")
                
            # Memory
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                self.warnings.append(f"⚠ High memory usage: {memory.percent}%")
            else:
                self.checks.append(f"✓ Memory usage: {memory.percent}%")
                
            # Disk
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                self.warnings.append(f"⚠ Low disk space: {disk.percent}% used")
            else:
                self.checks.append(f"✓ Disk usage: {disk.percent}%")
                
            return True
        except Exception as e:
            self.errors.append(f"✗ System resource check failed: {e}")
            return False
            
    def check_required_files(self):
        """Check if all required files exist"""
        required_files = [
            'src/bot.py',
            'src/link_analyzer.py',
            'src/ai_analyzer.py',
            'docker/Dockerfile',
            'requirements.txt'
        ]
        
        missing_files = []
        for file in required_files:
            if not os.path.exists(file):
                missing_files.append(file)
                
        if missing_files:
            self.errors.append(f"✗ Missing required files: {', '.join(missing_files)}")
            return False
        else:
            self.checks.append("✓ All required files present")
            return True
            
    async def run_health_check(self):
        """Run all health checks"""
        print("=" * 50)
        print("Discord Link Guardian Bot - Health Check")
        print("=" * 50)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("-" * 50)
        
        # Run checks
        checks_passed = all([
            await self.check_discord_connection(),
            await self.check_ai_provider(),
            self.check_database(),
            self.check_system_resources(),
            self.check_required_files()
        ])
        
        # Print results
        print("\n✓ PASSED CHECKS:")
        for check in self.checks:
            print(f"  {check}")
            
        if self.warnings:
            print("\n⚠ WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")
                
        if self.errors:
            print("\n✗ ERRORS:")
            for error in self.errors:
                print(f"  {error}")
                
        print("-" * 50)
        
        if self.errors:
            print("Status: UNHEALTHY ✗")
            return 1
        elif self.warnings:
            print("Status: HEALTHY WITH WARNINGS ⚠")
            return 0
        else:
            print("Status: HEALTHY ✓")
            return 0

async def main():
    checker = HealthChecker()
    exit_code = await checker.run_health_check()
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main())
