"""TikTok Ads MCP Server implementation."""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    ServerCapabilities,
    TextContent,
    Tool,
    ToolsCapability,
    LoggingCapability,
)

from .tiktok_client import TikTokAdsClient
from .tools import (
    CampaignTools,
    CreativeTools,
    PerformanceTools,
    AudienceTools,
    ReportingTools,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Server("tiktok-ads-mcp")


class TikTokMCPServer:
    """TikTok Ads MCP Server class."""

    def __init__(self):
        self.client: Optional[TikTokAdsClient] = None
        self.campaign_tools: Optional[CampaignTools] = None
        self.creative_tools: Optional[CreativeTools] = None
        self.performance_tools: Optional[PerformanceTools] = None
        self.audience_tools: Optional[AudienceTools] = None
        self.reporting_tools: Optional[ReportingTools] = None
        self.access_token: Optional[str] = None
        self.advertiser_id: Optional[str] = None

    async def initialize(self):
        """Initialize server — requires TIKTOK_ACCESS_TOKEN in environment."""
        self.access_token = os.getenv("TIKTOK_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError("Missing TIKTOK_ACCESS_TOKEN environment variable.")

        self.client = TikTokAdsClient(access_token=self.access_token)
        logger.info("TikTok Ads MCP Server initialized. Use tiktok_ads_switch_ad_account to select an advertiser.")

    def _init_tools(self):
        """(Re)initialize tool modules after advertiser is set."""
        self.campaign_tools = CampaignTools(self.client)
        self.creative_tools = CreativeTools(self.client)
        self.performance_tools = PerformanceTools(self.client)
        self.audience_tools = AudienceTools(self.client)
        self.reporting_tools = ReportingTools(self.client)

    async def get_auth_status(self) -> Dict[str, Any]:
        if self.advertiser_id:
            return {
                "success": True,
                "data": {
                    "status": "authenticated",
                    "advertiser_id": self.advertiser_id,
                    "message": "Authenticated and advertiser selected.",
                },
            }
        return {
            "success": True,
            "data": {
                "status": "token_set_no_advertiser",
                "message": "Access token is set but no advertiser selected. Use tiktok_ads_switch_ad_account to pick one.",
            },
        }

    async def switch_ad_account(self, advertiser_id: str) -> Dict[str, Any]:
        self.advertiser_id = advertiser_id
        self.client.advertiser_id = advertiser_id
        self._init_tools()
        logger.info(f"Switched to advertiser: {advertiser_id}")
        return {
            "success": True,
            "data": {
                "message": f"Now using advertiser account {advertiser_id}.",
                "advertiser_id": advertiser_id,
            },
        }


# Global server instance
tiktok_server = TikTokMCPServer()


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List all available TikTok Ads tools."""
    tools = [
        Tool(
            name="tiktok_ads_auth_status",
            description="Check current authentication status with TikTok Ads API",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        Tool(
            name="tiktok_ads_switch_ad_account",
            description="Switch to a different advertiser account. DO NOT switch automatically — only when the user asks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "advertiser_id": {"type": "string", "description": "The advertiser ID to use"}
                },
                "required": ["advertiser_id"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="tiktok_ads_get_campaigns",
            description="Retrieve all campaigns for the advertiser account",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["STATUS_ALL", "STATUS_NOT_DELETE", "STATUS_NOT_DELIVERY", "STATUS_DELIVERY_OK", "STATUS_DISABLE", "STATUS_DELETE"],
                        "description": "Filter campaigns by status",
                    },
                    "limit": {"type": "integer", "default": 10, "description": "Maximum number of campaigns to return"},
                },
            },
        ),
        Tool(
            name="tiktok_ads_get_campaign_details",
            description="Get detailed information about a specific campaign",
            inputSchema={
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "The campaign ID to retrieve details for"}
                },
                "required": ["campaign_id"],
            },
        ),
        Tool(
            name="tiktok_ads_get_adgroups",
            description="Retrieve ad groups for a campaign",
            inputSchema={
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID to get ad groups for"},
                    "status": {
                        "type": "string",
                        "enum": ["STATUS_ALL", "STATUS_NOT_DELETE", "STATUS_NOT_DELIVERY", "STATUS_DELIVERY_OK", "STATUS_DISABLE", "STATUS_DELETE"],
                        "description": "Filter ad groups by status",
                    },
                },
                "required": ["campaign_id"],
            },
        ),
        Tool(
            name="tiktok_ads_get_campaign_performance",
            description="Get performance metrics for campaigns",
            inputSchema={
                "type": "object",
                "properties": {
                    "campaign_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of campaign IDs to analyze",
                    },
                    "date_range": {
                        "type": "string",
                        "enum": ["today", "yesterday", "last_7_days", "last_14_days", "last_30_days"],
                        "description": "Date range for performance data",
                    },
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Metrics to include (e.g. spend, impressions, clicks, ctr, cpc, cpm, conversions, cost_per_conversion)",
                    },
                },
                "required": ["campaign_ids", "date_range"],
            },
        ),
        Tool(
            name="tiktok_ads_get_adgroup_performance",
            description="Get performance metrics for ad groups",
            inputSchema={
                "type": "object",
                "properties": {
                    "adgroup_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of ad group IDs to analyze",
                    },
                    "date_range": {
                        "type": "string",
                        "enum": ["today", "yesterday", "last_7_days", "last_14_days", "last_30_days"],
                        "description": "Date range for performance data",
                    },
                    "breakdowns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Data breakdowns: age, gender, country, placement",
                    },
                },
                "required": ["adgroup_ids", "date_range"],
            },
        ),
    ]
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls for TikTok Ads operations."""
    try:
        if name == "tiktok_ads_auth_status":
            result = await tiktok_server.get_auth_status()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "tiktok_ads_switch_ad_account":
            result = await tiktok_server.switch_ad_account(arguments["advertiser_id"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # All other tools require an advertiser to be selected
        if not tiktok_server.advertiser_id:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": "No advertiser selected. Use tiktok_ads_switch_ad_account to pick an advertiser ID first."
                }),
            )]

        result = None

        if name == "tiktok_ads_get_campaigns":
            result = await tiktok_server.campaign_tools.get_campaigns(**arguments)
        elif name == "tiktok_ads_get_campaign_details":
            result = await tiktok_server.campaign_tools.get_campaign_details(**arguments)
        elif name == "tiktok_ads_create_campaign":
            result = await tiktok_server.campaign_tools.create_campaign(**arguments)
        elif name == "tiktok_ads_get_adgroups":
            result = await tiktok_server.campaign_tools.get_adgroups(**arguments)
        elif name == "tiktok_ads_create_adgroup":
            result = await tiktok_server.campaign_tools.create_adgroup(**arguments)
        elif name == "tiktok_ads_get_campaign_performance":
            result = await tiktok_server.performance_tools.get_campaign_performance(**arguments)
        elif name == "tiktok_ads_get_adgroup_performance":
            result = await tiktok_server.performance_tools.get_adgroup_performance(**arguments)
        elif name == "tiktok_ads_get_ad_creatives":
            result = await tiktok_server.creative_tools.get_ad_creatives(**arguments)
        elif name == "tiktok_ads_upload_image":
            result = await tiktok_server.creative_tools.upload_image(**arguments)
        elif name == "tiktok_ads_get_custom_audiences":
            result = await tiktok_server.audience_tools.get_custom_audiences(**arguments)
        elif name == "tiktok_ads_get_targeting_options":
            result = await tiktok_server.audience_tools.get_targeting_options(**arguments)
        elif name == "tiktok_ads_generate_report":
            result = await tiktok_server.reporting_tools.generate_report(**arguments)
        else:
            return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]

        return [TextContent(type="text", text=str(result))]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]


async def main():
    """Main entry point for the TikTok Ads MCP server."""
    await tiktok_server.initialize()

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="tiktok-ads-mcp",
                server_version="1.0.0",
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(listChanged=True),
                    logging=LoggingCapability(),
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
