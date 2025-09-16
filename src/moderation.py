import discord
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ModerationSystem:
    def __init__(self, database, config):
        self.db = database
        self.config = config
        
    async def add_warning(
        self, 
        guild_id: int, 
        user_id: int, 
        reason: str, 
        channel_id: int = None
    ) -> int:
        """Add a warning and return total count"""
        count = await self.db.add_warning(guild_id, user_id, reason, channel_id)
        logger.info(f"Warning added for user {user_id} in guild {guild_id}. Total: {count}")
        return count
        
    async def get_warnings(self, guild_id: int, user_id: int) -> list:
        """Get user warnings"""
        return await self.db.get_warnings(guild_id, user_id)
        
    async def mute_user(
        self, 
        guild: discord.Guild, 
        member: discord.Member, 
        duration_days: int = 15,
        reason: str = None
    ):
        """Mute a user"""
        # Create muted role if it doesn't exist
        muted_role = discord.utils.get(guild.roles, name="Muted")
        
        if not muted_role:
            muted_role = await guild.create_role(
                name="Muted",
                permissions=discord.Permissions(
                    send_messages=False,
                    add_reactions=False,
                    speak=False
                )
            )
            
            # Set permissions for all channels
            for channel in guild.channels:
                await channel.set_permissions(
                    muted_role,
                    send_messages=False,
                    add_reactions=False,
                    speak=False
                )
                
        # Add role to member
        await member.add_roles(muted_role, reason=reason)
        
        # Add to database
        mute_end = datetime.now() + timedelta(days=duration_days)
        await self.db.add_mute(guild.id, member.id, mute_end, reason)
        
        logger.info(f"User {member.id} muted until {mute_end}")
        
    async def unmute_user(self, guild: discord.Guild, member: discord.Member):
        """Unmute a user"""
        muted_role = discord.utils.get(guild.roles, name="Muted")
        
        if muted_role and muted_role in member.roles:
            await member.remove_roles(muted_role)
            
        await self.db.remove_mute(guild.id, member.id)
        logger.info(f"User {member.id} unmuted")
        
    async def is_user_muted(self, guild_id: int, user_id: int) -> bool:
        """Check if user is muted"""
        mutes = await self.db.get_active_mutes(guild_id)
        return any(m[2] == user_id for m in mutes)
        
    async def check_expired_mutes(self, bot):
        """Check and remove expired mutes"""
        for guild in bot.guilds:
            mutes = await self.db.get_active_mutes(guild.id)
            
            for mute in mutes:
                mute_end = datetime.fromisoformat(mute[3])
                if datetime.now() > mute_end:
                    member = guild.get_member(mute[2])
                    if member:
                        await self.unmute_user(guild, member)
