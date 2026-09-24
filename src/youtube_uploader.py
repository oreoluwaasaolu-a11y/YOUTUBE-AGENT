import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from src import config
from src.utils import logger, print_banner


class YouTubeUploader:
    """Handles OAuth 2.0 authentication with persistent token storage and direct YouTube upload."""

    def __init__(
        self,
        client_secrets_file: Path = config.CLIENT_SECRET_FILE,
        token_file: Path = config.TOKEN_FILE,
        scopes: Optional[List[str]] = None,
    ):
        self.client_secrets_file = client_secrets_file
        self.token_file = token_file
        self.scopes = scopes or config.YOUTUBE_SCOPES
        self.service = None

    def authenticate(self) -> Any:
        """
        Authenticate via OAuth 2.0. Loads and refreshes token.json or runs local server flow.
        """
        creds: Optional[Credentials] = None

        # 1. Check if token.json already exists
        if self.token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_file), self.scopes)
                logger.info("[green]✓ Loaded persistent session credentials from token.json[/green]")
            except Exception as e:
                logger.warning(f"Failed to load existing token.json: {e}")
                creds = None

        # 2. Refresh or request new credentials if invalid
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("[cyan]Refreshing expired access token...[/cyan]")
                try:
                    creds.refresh(Request())
                    logger.info("[green]✓ Token refreshed successfully.[/green]")
                except Exception as e:
                    logger.warning(f"Could not refresh token: {e}. Re-authenticating...")
                    creds = None

            if not creds:
                if not self.client_secrets_file.exists():
                    raise FileNotFoundError(
                        f"client_secret.json not found at {self.client_secrets_file}! "
                        "Please provide your Google Cloud OAuth 2.0 client credentials."
                    )
                
                logger.info("[bold yellow]Opening browser for one-time YouTube OAuth authentication...[/bold yellow]")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.client_secrets_file), self.scopes
                )
                creds = flow.run_local_server(port=0)

            # 3. Save persistent token.json
            with open(self.token_file, "w") as token:
                token.write(creds.to_json())
            logger.info(f"[green]✓ Saved persistent session credentials to {self.token_file.name}[/green]")

        self.service = build("youtube", "v3", credentials=creds)
        return self.service

    def upload_short(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        privacy_status: Optional[str] = None,
        category_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Uploads video to YouTube with resumable chunk upload and returns video metadata & Short URL.
        """
        if not self.service:
            self.authenticate()

        # Ensure title has #Shorts
        if "#Shorts" not in title and "#shorts" not in title:
            title = f"{title} #Shorts"

        # Truncate title to YouTube 100 char limit
        title = title[:100]

        privacy = privacy_status or config.DEFAULT_PRIVACY_STATUS
        cat_id = category_id or config.YOUTUBE_CATEGORY_ID
        tag_list = tags or ["Shorts", "YouTubeShorts", "Viral"]

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tag_list,
                "categoryId": cat_id,
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        logger.info(f"[bold cyan]Uploading video to YouTube ({privacy}):[/bold cyan] [bold]{title}[/bold]")
        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            chunksize=1024 * 1024 * 4,  # 4MB chunks
            resumable=True
        )

        request = self.service.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )

        response = None
        retry_count = 0
        max_retries = 5

        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"[cyan]Upload Progress: {progress}%[/cyan]")
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    retry_count += 1
                    if retry_count > max_retries:
                        raise e
                    sleep_sec = 2 ** retry_count
                    logger.warning(f"HTTP {e.resp.status} error during upload. Retrying in {sleep_sec}s...")
                    time.sleep(sleep_sec)
                else:
                    raise e
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    raise e
                time.sleep(3)

        video_id = response.get("id")
        short_url = f"https://youtube.com/shorts/{video_id}"
        watch_url = f"https://www.youtube.com/watch?v={video_id}"

        print_banner(
            "🎉 YOUTUBE SHORT UPLOAD COMPLETE!",
            f"Video ID: {video_id}\nShorts URL: {short_url}\nWatch URL: {watch_url}"
        )

        return {
            "id": video_id,
            "short_url": short_url,
            "watch_url": watch_url,
            "title": title,
            "privacy_status": privacy
        }

    def update_channel_info(
        self, new_title: str, new_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch current channel and update channel title and description branding settings.
        """
        if not self.service:
            self.authenticate()

        logger.info(f"[cyan]Fetching authenticated YouTube channel details...[/cyan]")
        channels_response = self.service.channels().list(
            part="brandingSettings,snippet",
            mine=True
        ).execute()

        items = channels_response.get("items", [])
        if not items:
            raise ValueError("No YouTube channel found for the authenticated Google Account!")

        channel = items[0]
        channel_id = channel.get("id")
        current_title = channel.get("snippet", {}).get("title", "Unknown")
        logger.info(f"[cyan]Current Channel:[/cyan] [bold]{current_title}[/bold] (ID: {channel_id})")

        branding = channel.get("brandingSettings", {})
        if "channel" not in branding:
            branding["channel"] = {}

        branding["channel"]["title"] = new_title
        if new_description:
            branding["channel"]["description"] = new_description

        try:
            update_response = self.service.channels().update(
                part="brandingSettings",
                body={
                    "id": channel_id,
                    "brandingSettings": branding
                }
            ).execute()
            logger.info(f"[bold green]✓ Channel branding updated to:[/bold green] [bold]{new_title}[/bold]")
            return update_response
        except Exception as e:
            logger.warning(
                f"[yellow]Note: YouTube API may require channel name changes directly via YouTube Studio depending on account type. Error: {e}[/yellow]"
            )
            return {"status": "manual_or_error", "message": str(e)}
