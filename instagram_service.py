import json
import re
import requests

from bs4 import BeautifulSoup


class InstagramService:

    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/142.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,image/avif,image/webp,"
                "image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })

    # ---------------------------------------------------------
    # MAIN METHOD
    # ---------------------------------------------------------

    def get_profile(self, username):

        username = username.strip().lstrip("@")

        if not username:
            raise ValueError("Username is required")

        url = f"https://www.instagram.com/{username}/"

        response = self.session.get(
            url,
            timeout=20,
            allow_redirects=True
        )

        response.raise_for_status()

        html = response.text

        # Save response for debugging
        with open("instagram_response.html", "w", encoding="utf-8") as file:
            file.write(html)

        # Check whether Instagram returned an error page
        if "PolarisErrorRoute" in html:
            raise Exception("Instagram returned an error page")

        profile = self.parse_profile(html, username)

        if not profile:
            raise Exception(
                f"Could not find Instagram profile: {username}"
            )

        return profile

    # ---------------------------------------------------------
    # PARSE PROFILE
    # ---------------------------------------------------------

    def parse_profile(self, html, username):

        soup = BeautifulSoup(html, "html.parser")

        profile_data = None

        # Instagram currently keeps profile information
        # inside application/json script tags.
        scripts = soup.find_all(
            "script",
            attrs={"type": "application/json"}
        )

        for script in scripts:

            script_text = script.string

            if not script_text:
                script_text = script.get_text()

            if not script_text:
                continue

            try:
                data = json.loads(script_text)

            except (json.JSONDecodeError, TypeError):
                continue

            profile_data = self.find_profile_object(
                data,
                username
            )

            if profile_data:
                break

        # -----------------------------------------------------
        # Extract OG metadata as fallback
        # -----------------------------------------------------

        og_description = self.get_meta_content(
            soup,
            "property",
            "og:description"
        )

        og_title = self.get_meta_content(
            soup,
            "property",
            "og:title"
        )

        og_image = self.get_meta_content(
            soup,
            "property",
            "og:image"
        )

        # -----------------------------------------------------
        # If embedded JSON was found
        # -----------------------------------------------------

        if profile_data:

            posts = profile_data.get("all_media_count")

            # Instagram currently returns all_media_count as null
            # in the profile object, so use OG description.
            if posts is None:
                posts = self.extract_posts_from_description(
                    og_description
                )

            return {
                "username": profile_data.get("username"),
                "full_name": profile_data.get("full_name"),
                "followers": profile_data.get("follower_count"),
                "following": profile_data.get("following_count"),
                "posts": posts,
                "description": profile_data.get("biography"),
                "profile_image": (
                    profile_data.get("profile_pic_url")
                    or og_image
                ),
                "is_verified": profile_data.get("is_verified"),
                "is_private": profile_data.get("is_private"),
                "has_any_clips": profile_data.get("has_any_clips"),
                "instagram_id": profile_data.get("id"),
                "pk": profile_data.get("pk"),
                "latest_reel_media": profile_data.get(
                    "latest_reel_media"
                )
            }

        # -----------------------------------------------------
        # Fallback when JSON profile data isn't found
        # -----------------------------------------------------

        return self.parse_from_og(
            username=username,
            description=og_description,
            title=og_title,
            image=og_image
        )

    # ---------------------------------------------------------
    # FIND PROFILE OBJECT RECURSIVELY
    # ---------------------------------------------------------

    def find_profile_object(self, data, username):

        if isinstance(data, dict):

            current_username = data.get("username")

            if (
                current_username
                and current_username.lower() == username.lower()
                and (
                    "follower_count" in data
                    or "following_count" in data
                    or "biography" in data
                )
            ):
                return data

            for value in data.values():

                result = self.find_profile_object(
                    value,
                    username
                )

                if result:
                    return result

        elif isinstance(data, list):

            for item in data:

                result = self.find_profile_object(
                    item,
                    username
                )

                if result:
                    return result

        return None

    # ---------------------------------------------------------
    # OG META CONTENT
    # ---------------------------------------------------------

    @staticmethod
    def get_meta_content(
        soup,
        attribute,
        value
    ):

        tag = soup.find(
            "meta",
            attrs={attribute: value}
        )

        if tag:
            return tag.get("content")

        return None

    # ---------------------------------------------------------
    # EXTRACT POSTS FROM OG DESCRIPTION
    # ---------------------------------------------------------

    @staticmethod
    def extract_posts_from_description(description):

        if not description:
            return None

        match = re.search(
            r"([\d,.]+[KMB]?)\s+Posts",
            description,
            re.IGNORECASE
        )

        if not match:
            return None

        posts = match.group(1)

        # Convert simple numeric values such as:
        # 1,618 -> 1618

        if posts.replace(",", "").replace(".", "").isdigit():
            try:
                return int(posts.replace(",", ""))
            except ValueError:
                pass

        return posts

    # ---------------------------------------------------------
    # FALLBACK OG PARSER
    # ---------------------------------------------------------

    def parse_from_og(
        self,
        username,
        description,
        title,
        image
    ):

        followers = None
        following = None
        posts = None

        if description:

            followers_match = re.search(
                r"([\d,.]+[KMB]?)\s+Followers",
                description,
                re.IGNORECASE
            )

            following_match = re.search(
                r"([\d,.]+[KMB]?)\s+Following",
                description,
                re.IGNORECASE
            )

            posts_match = re.search(
                r"([\d,.]+[KMB]?)\s+Posts",
                description,
                re.IGNORECASE
            )

            if followers_match:
                followers = self.convert_count(
                    followers_match.group(1)
                )

            if following_match:
                following = self.convert_count(
                    following_match.group(1)
                )

            if posts_match:
                posts = self.convert_count(
                    posts_match.group(1)
                )

        full_name = None

        if title:

            match = re.match(
                r"(.+?)\s+\(@",
                title
            )

            if match:
                full_name = match.group(1)

        return {
            "username": username,
            "full_name": full_name,
            "followers": followers,
            "following": following,
            "posts": posts,
            "description": None,
            "profile_image": image,
            "is_verified": None,
            "is_private": None,
            "has_any_clips": None,
            "instagram_id": None,
            "pk": None,
            "latest_reel_media": None
        }

    # ---------------------------------------------------------
    # CONVERT 73M / 1.2K / 1,618
    # ---------------------------------------------------------

    @staticmethod
    def convert_count(value):

        if not value:
            return None

        value = value.strip().upper()

        try:

            if value.endswith("B"):
                return int(float(value[:-1]) * 1_000_000_000)

            if value.endswith("M"):
                return int(float(value[:-1]) * 1_000_000)

            if value.endswith("K"):
                return int(float(value[:-1]) * 1_000)

            return int(value.replace(",", ""))

        except ValueError:
            return value