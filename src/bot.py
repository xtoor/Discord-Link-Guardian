import discord
from discord.ext import commands, tasks
import asyncio
import logging
import yaml
import re
from datetime import datetime, timedelta
from typing import Optional, List
import aiohttp

from link_analyzer import LinkAnalyzer
from ai_analyzer import AIAnalyzer
from moderation import ModerationSystem
from database import Database
from config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LinkGuardianBot(commands.Bot):
    def __init__(self, config_path: str):
        self.config = Config(config_path)
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix=self.config.get('bot.prefix', '!'),
            intents=intents
        )
        
        self.db = Database(self.config.get('database.path', 'data/bot.db'))
        self.link_analyzer = LinkAnalyzer(self.config)
        self.ai_analyzer = AIAnalyzer(self.config)
        self.moderation = ModerationSystem(self.db, self.config)
        
        # URL regex pattern
        self.url_pattern = re.compile(
            r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b'
            r'(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'
        )
        
    async def setup_hook(self):
        """Initialize bot components"""
        await self.db.initialize()
        await self.load_extensions()
        self.check_mutes.start()
        
    async def load_extensions(self):
        """Load bot cogs/extensions"""
        # Add any additional cogs here
        pass
        
    @tasks.loop(minutes=1)
    async def check_mutes(self):
        """Check and remove expired mutes"""
        await self.moderation.check_expired_mutes(self)
        
    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for suspicious links"
            )
        )
        
    async def on_message(self, message: discord.Message):
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Check if user is muted
        if await self.moderation.is_user_muted(message.guild.id, message.author.id):
            try:
                await message.delete()
                return
            except discord.Forbidden:
                logger.warning(f"Cannot delete message from muted user {message.author.id}")
                
        # Find URLs in message
        urls = self.url_pattern.findall(message.content)
        
        if urls:
            await self.process_links(message, urls)
            
        await self.process_commands(message)
        
    async def process_links(self, message: discord.Message, urls: List[str]):
        """Process and analyze links in a message"""
        for url in urls:
            logger.info(f"Analyzing URL: {url} from {message.author}")
            
            # Show analyzing message
            embed = discord.Embed(
                title="🔍 Analyzing Link",
                description=f"Checking: {url[:50]}...",
                color=discord.Color.yellow()
            )
            status_msg = await message.channel.send(embed=embed)
            
            try:
                # Analyze the link
                analysis_result = await self.analyze_link(url)
                
                # Handle based on threat level
                await self.handle_analysis_result(
                    message, 
                    url, 
                    analysis_result, 
                    status_msg
                )
                
            except Exception as e:
                logger.error(f"Error analyzing link {url}: {e}")
                await status_msg.edit(embed=discord.Embed(
                    title="⚠️ Analysis Error",
                    description="Could not complete link analysis",
                    color=discord.Color.orange()
                ))
                
    async def analyze_link(self, url: str) -> dict:
        """Comprehensive link analysis"""
        result = {
            'url': url,
            'threat_level': 'unknown',  # safe, suspicious, danger, unknown
            'confidence': 0.0,
            'reasons': [],
            'details': {}
        }
        
        # Basic link analysis (domain reputation, SSL, etc.)
        basic_analysis = await self.link_analyzer.analyze(url)
        result['details']['basic'] = basic_analysis
        
        # AI-powered analysis
        ai_analysis = await self.ai_analyzer.analyze(url, basic_analysis)
        result['details']['ai'] = ai_analysis
        
        # Determine overall threat level
        result['threat_level'] = self.determine_threat_level(basic_analysis, ai_analysis)
        result['confidence'] = (basic_analysis.get('confidence', 0) + 
                               ai_analysis.get('confidence', 0)) / 2
        result['reasons'] = basic_analysis.get('flags', []) + ai_analysis.get('flags', [])
        
        return result
        
    def determine_threat_level(self, basic: dict, ai: dict) -> str:
        """Determine overall threat level from analyses"""
        basic_score = basic.get('threat_score', 0)
        ai_score = ai.get('threat_score', 0)
        
        avg_score = (basic_score + ai_score) / 2
        
        if avg_score >= 0.8:
            return 'danger'
        elif avg_score >= 0.5:
            return 'suspicious'
        elif avg_score >= 0.2:
            return 'caution'
        else:
            return 'safe'
            
    async def handle_analysis_result(
        self, 
        message: discord.Message, 
        url: str, 
        result: dict,
        status_msg: discord.Message
    ):
        """Handle the analysis result with appropriate actions"""
        threat_level = result['threat_level']
        confidence = result['confidence']
        reasons = result['reasons']
        
        if threat_level == 'danger' and confidence > 0.7:
            # Delete message and warn user
            try:
                await message.delete()
            except discord.Forbidden:
                logger.warning(f"Cannot delete message containing dangerous link")
                
            # Add warning to user
            warning_count = await self.moderation.add_warning(
                message.guild.id,
                message.author.id,
                f"Posted dangerous link: {url[:50]}...",
                message.channel.id
            )
            
            # Create danger embed
            embed = discord.Embed(
                title="🚫 Dangerous Link Detected",
                description=f"**User:** {message.author.mention}\n"
                           f"**Link:** `{url[:50]}...`\n"
                           f"**Warning #{warning_count}/3**",
                color=discord.Color.red()
            )
            
            if reasons:
                embed.add_field(
                    name="Reasons",
                    value="\n".join(f"• {r}" for r in reasons[:5]),
                    inline=False
                )
                
            await status_msg.edit(embed=embed)
            
            # Notify admins
            await self.notify_admins(message.guild, embed)
            
            # Check if user should be muted
            if warning_count >= 3:
                await self.moderation.mute_user(
                    message.guild,
                    message.author,
                    duration_days=15,
                    reason="3 warnings for posting dangerous links"
                )
                
        elif threat_level == 'suspicious':
            embed = discord.Embed(
                title="⚠️ Suspicious Link Detected",
                description=f"**@everyone** Proceed with caution!\n"
                           f"Link: `{url[:50]}...`\n"
                           f"Confidence: {confidence:.1%}",
                color=discord.Color.orange()
            )
            
            if reasons:
                embed.add_field(
                    name="Concerns",
                    value="\n".join(f"• {r}" for r in reasons[:3]),
                    inline=False
                )
                
            await status_msg.edit(embed=embed)
            
        elif threat_level == 'caution':
            embed = discord.Embed(
                title="ℹ️ Proceed with Caution",
                description=f"Limited information available for this link.\n"
                           f"Link: `{url[:50]}...`",
                color=discord.Color.yellow()
            )
            await status_msg.edit(embed=embed)
            
        else:  # safe
            embed = discord.Embed(
                title="✅ Link Appears Safe",
                description=f"No immediate threats detected.\n"
                           f"Link: `{url[:50]}...`",
                color=discord.Color.green()
            )
            await status_msg.edit(embed=embed)
            
            # Delete status message after 10 seconds for safe links
            await asyncio.sleep(10)
            try:
                await status_msg.delete()
            except:
                pass
                
    async def notify_admins(self, guild: discord.Guild, embed: discord.Embed):
        """Notify server admins about dangerous links"""
        admin_role = discord.utils.get(guild.roles, name="Admin")
        if not admin_role:
            admin_role = discord.utils.get(guild.roles, name="admin")
            
        if admin_role:
            embed.description = f"{admin_role.mention}\n" + embed.description
            
        # Try to find an admin channel
        admin_channel = discord.utils.get(guild.text_channels, name="admin-logs")
        if not admin_channel:
            admin_channel = discord.utils.get(guild.text_channels, name="logs")
            
        if admin_channel:
            await admin_channel.send(embed=embed)

# Bot commands
@commands.command(name='warnings')
async def check_warnings(ctx, member: Optional[discord.Member] = None):
    """Check warnings for a user"""
    if member is None:
        member = ctx.author
        
    warnings = await ctx.bot.moderation.get_warnings(ctx.guild.id, member.id)
    
    embed = discord.Embed(
        title=f"Warnings for {member.display_name}",
        color=discord.Color.blue()
    )
    
    if warnings:
        for i, warning in enumerate(warnings, 1):
            embed.add_field(
                name=f"Warning {i}",
                value=f"**Reason:** {warning['reason']}\n"
                      f"**Date:** {warning['timestamp']}",
                inline=False
            )
    else:
        embed.description = "No warnings found."
        
    await ctx.send(embed=embed)

@commands.command(name='unmute')
@commands.has_permissions(manage_roles=True)
async def unmute_user(ctx, member: discord.Member):
    """Unmute a user"""
    await ctx.bot.moderation.unmute_user(ctx.guild, member)
    await ctx.send(f"✅ {member.mention} has been unmuted.")
