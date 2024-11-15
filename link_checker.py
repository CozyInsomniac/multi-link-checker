"""Python link checker for various file hosting websites."""
#===================================================================================================
# Standard Libraries
from __future__ import annotations

from contextlib import contextmanager
from logging import DEBUG, INFO, Logger, basicConfig, getLogger
from pathlib import Path
from random import randint
from signal import SIGALRM, alarm, signal
from sys import argv, exit
from typing import Callable

from pathos.multiprocessing import ProcessingPool as Pool
from regex import Pattern, compile
from requests import Response, post
from requests import get as reqget
from tqdm import tqdm

#===================================================================================================

class LinkChecker:
    """Link checker class."""

    def __init__(self, input_file: str = "") -> None:
        """Initialize the checker."""
        if not input_file:
            return

        # Dict of supported sites + their validation type
        # 1 = Custom calidation
        # 2 = 200 response code validation
        # 3 = Paste site calidation
        self.supported_sites: dict[str, int] = {
            "mega.nz":          1,
            "mega.co.nz":       1,
            "imgspice.com":     1,
            "imageporter.com":  1,
            "4shared.com":      1,
            "bunkrr":           1,
            "gofile.io":        1,
            "cyberfile.me":     1,
            "ibb.co":           2,
            "upfiles.com":      2,
            "files.catbox.moe": 2,
            "puu.sh":           2,
            "pixeldrain.com":   2,
            "mediafire.com":    2,
            "stream.bunkr.is":  2,
            "bunkr.is":         2,
            "drive.google.com": 2,
            "sendvid":          2,
            "cyberdrop.me":     2,
            "justpaste.it":     3,
            "pastebin.com":     3,
            "rentry.co":        3,
            "paste.ee":         3,
            "bitbin.it":        3,
            "anonpaste.io":     3,
            "telegra.ph":       3,
            "paste.gg":         3,
            "paster.so":        3,
        }


        # Lambdas to fix redirecting sites / get the raw version of paste sites
        self.link_fixers: dict[str,Callable[str]] = {
            "pastebin.com": lambda url: url.replace("pastebin.com", "pastebin.com/raw"),
            "rentry.co": lambda url: f"{url}raw",
            "bunkrr.su": lambda url: url.replace("bunkrr.su", "bunkrr.si"),
        }


        # Strings
        self.forbidden_strings: list[str] = [
            ".exe",
            ".msi",
            ".mp4",
            "pixl.is",
            "redirect",
            "uploadbank.com",
            "filesfly.cc",
            "direct-link",
            "t.me",
        ]

        # Regex to find URLs in input
        url_regex_pattern: str = f"(https://)(www.)?({"|".join(self.supported_sites)})(/[^ \t\r\n\"\"><();,]+)+"
        self.url_regex: Pattern = compile(url_regex_pattern)

        # Regex to find forbidden strings
        self.forbidden_regex: Pattern = compile(("|".join(self.forbidden_strings)).replace(".",r"\."))

        # Output file names
        self.bad_output_file: str = "bad_urls.txt"
        self.good_output_file: str = "good_urls.txt"
        self.input_file: str = input_file

        # Multiprocessing variables
        self.pool: Pool = None
        self.results: list = []

        # Statistics variables
        self.seen_urls_dict: dict[str: 1] = self.get_seen_urls()    # Hashmap for previous seen URLs
        self.seen_url_count: int = len(self.seen_urls_dict.keys())  # Count of previous seen URLs
        self.raw_line_count: int = 0                        # Linecount of input file
        self.good_url_count: int = 0                        # Count of previously seen, working URLs
        self.bad_url_count: int = 0                         # Count of previously seen,

        # Logger variables
        self.logger: Logger = getLogger()
        basicConfig(level=DEBUG)


# ==================================================================================================
# Implementation functions

    def main(self) -> None:
        """Check the links."""
        # Get raw url count
        self.logger.info(f"Total previously seen URLs: {self.seen_url_count}")

        # Get input URLs
        input_urls: list = self.compile_url_list()
        self.logger.info(f"Valid, unseen, unique input URLs: {len(input_urls)}")

        # Test input urls
        self.test_url_list(input_urls)
        self.web_driver.quit()


    def compile_url_list(self) -> list[str]:
            """Compile a list of supported, valid URLs for checking.

            Returns
            -------
                list: List of valid URLs

            """
            # Extract URLs from the input file for parsing
            self.logger.info("Compiling input URLs...")
            with Path.open(self.input_file, "r") as input_url_file:
                self.logger.info(f"Raw input lines: {len(input_url_file.readlines())}")
                input_url_file.seek(0)
                valid_urls: set[str] = self.get_valid_urls(self.get_raw_urls(input_url_file.read()))


            # Unpack URLs from paste sites
            parsed_valid_urls: set[str] = set({})
            for url in tqdm(valid_urls):
                if self.is_paste_url(url):
                    parsed_valid_urls.update(self.parse_paste_url(url))
                else:
                    parsed_valid_urls.add(url)

            return list(parsed_valid_urls)


    def get_raw_urls(self, input_string: str) -> set[str]:
        """Extract URLs from the input file.

        Args:
        ----
            input_string (str): Input string from the input file.

        Returns:
        -------
            set: List of extracted URLs.

        """
        input_string = input_string.replace("http", " http").replace("mega.co.nz", "mega.nz")
        raw_url_set: set[str] = {"".join(url) for url in self.url_regex.findall(input_string)}

        #self.logger.info(f"URLs from raw input: {len(raw_url_set)}")

        return raw_url_set


    def get_valid_urls(self, input_list: set[str]) -> set[str]:
        """Get and return all valid URLs of a list.

        Args:
        ----
            input_list (list|set): Input list of URLs

        Returns:
        -------
            list: Output list of valid URLs

        """
        valid_urls: set[str] = {url for url in input_list if self.is_valid(url)}
        return valid_urls


    def get_seen_urls(self) -> dict[str, 1]:
        """Compile a dict of all seen URLs for O(1) duplicate URL lookup time.

        Returns
        -------
            dict: List of all previously seen URLs

        """
        with\
        Path.open(f"output/{self.good_output_file}") as good_urls,\
        Path.open(f"output/{self.bad_output_file}") as bad_urls:
            return {url.strip("\n"):1 for url in (good_urls.readlines() + bad_urls.readlines())}


    def is_valid(self, url: str) -> bool:
        """Determine if a URL is both valid and unseen.

        Args:
        ----
            url (str): URL to test

        Returns:
        -------
            bool: True = valid. False = invalid / seen.

        """
        return bool(not self.forbidden_regex.search(url) and not self.seen_urls_dict.get(url))


    def test_url_list(self, input_urls: list[str]) -> None:
        """Test if a list of URLs are alive.

        Args:
        ----
            input_urls (list): List of URLs to test

        """
        self.logger.info("Testing URLs...")

        with\
        Path.open(f"output/{self.good_output_file}", "a+", encoding="utf-8") as good_urls,\
        Path.open(f"output/{self.bad_output_file}", "a+", encoding="utf-8") as bad_urls,\
        Pool(processes=6) as self.pool:

            # Use multiprocessing to process each URL
            for i, result in enumerate(tqdm(self.pool.imap(self.test_single_url, input_urls),\
            total = len(input_urls))):

                # Good URL processed
                if result:
                    self.bad_url_count += 1
                    self.write_file(bad_urls, input_urls[i])

                # Bad URL processed
                else:
                    self.good_url_count += 1
                    self.write_file(good_urls, input_urls[i])

            # Status report
            self.logger.info(f"Input URLs: {len(input_urls)}")
            self.logger.info(f"Good URLs: {self.good_url_count}")
            self.logger.info(f"Bad URLs: {self.bad_url_count}")


    def test_single_url(self, url: str) -> int:
        """Test a single URL.

        Args:
        ----
            url (str): URL to test

        Returns:
        -------
            int: 0 if Valid URL, 1 if Bad URL.

        """
        try:
            with self.time_limit(10):

                # Reject paste URLs
                if any(string in url for string in ["paste", "rentry", "bitbin"]):
                    #self.logger.debug(f"{url} is paste site")
                    return 1

                # Attempt to get a response from the URL
                resp: Response = reqget(url, timeout=20)

                # Invalid or no response handler
                if (not resp or resp.status_code != 200):
                    #self.logger.debug(f"{url} returned error status code.")
                    return 1

                # Valid response + link guarenteed good in 200 response code handler
                if any(item in url and self.supported_sites.get(item) == 2 for item in self.supported_sites):
                    return 0

                # Mega Links
                if ("mega" in url):
                    self.logger.debug(f"URL '{url}' is Mega")
                    return (0 if (self.mega_is_valid(self.fix_mega_url(url))) else 1)

                # Other links
                self.logger.debug(f"URL '{url}' is other")
                return not bool(\

                    ("imgspice" in url and len(resp.text) != 4924) or\

                    ("imageporter" in url and "No file" not in resp.text) or\

                    ("4shared" in url\
                    and "You need owner's permission to access this folder." not in resp.text\
                    and "The file link that you requested is not valid." not in resp.text) or\

                    ("ibb.co" in url\
                    and ("That page doesn" not in resp.text
                    and "There's nothing to show here" not in resp.text)) or\

                    ("gofile.io" in url and len(resp.text) != 1158) or\

                    ("cyberfile.me" in url and len(resp.text) != 12094) or\

                    ("bunkrr.su" in url and "a twerking taco" not in resp.text),
                )

        except BaseException:
            self.logger.exception(f"{url} timed out or caused error.")
            return 1


    @contextmanager
    def time_limit(self, seconds: int) -> None:
        """Time limit for how long a URL can take to be parsed before being considered "timed out".

        Args:
        ----
            seconds (int): Max seconds a URL can take to be parsed

        """

        def signal_handler() -> None:
            msg: str = "Timed out!"
            raise ConnectionError(msg)

        signal(SIGALRM, signal_handler)
        alarm(seconds)
        try:
            yield
        finally:
            alarm(0)


    def mega_is_valid(self, url: str) -> bool:
        """Determine if MEGA link is valid.

        Args:
        ----
            url (str): Link to check.

        Returns:
        -------
            bool: True = valid. False = Invalid.

        """
        api_url: str = "https://g.api.mega.co.nz/cs"
        url_type: list[str] = url.split("/")[3]
        url_id: list[str] = url.split("/")[4].split("#")[0]

        data:dict[int,str|int] =  {
                "a":"f",
                "c":1,
                "r":1,
                "ca":1,
                } if url_type == "folder" else {"a": "g", "p": url_id}

        params: dict[str, str] = {
                "id": "".join([f"{randint(0, 9)}" for num in range(10)]),  # noqa: S311
                "n": url_id,
                }

        resp: Response = post(api_url, params=params, data=data, timeout=10)
        return (resp.json() == -2)


   





    def is_paste_url(self, url: str) -> bool:
        """Check is a URL is a paste site.

        Args:
        ----
            url (str): URL to test.

        Returns:
        -------
            bool: True = is paste URL. False = is not paste url

        """
        for item in self.supported_sites:
            if (item in url and self.supported_sites.get(item) == 3):
                return True

        return False


    def parse_paste_url(self, url: str) -> set:
        """Parse links from a paste site URL.

        Args:
        ----
            url (str): Paste site URL

        Returns:
        -------
            list: List of links parsed from the paste site

        """
        # Try to extract URLs from paste url
        try:
            return set(self.get_valid_urls(self.get_raw_urls(reqget(self.fix_url(url),\
            timeout=10).text)))

        except Exception:
            self.logger.exception("Error extracting paste URLs.")
            return []


    def fix_url(self, url: str) -> str:
        """Fix a url to remove any redirects.

        Args:
        ----
            url (str): _description_

        Returns:
        -------
            str: _description_

        """
        for fixer_url in self.link_fixers:
            if fixer_url in url:
                fixer: Callable[str] = self.link_fixers.get(fixer_url)
                return fixer(url)

        return url


    def fix_mega_url(self, url: str) -> str:
        """Fix a mega link to remove redirects.

        Args:
        ----
            url (str): URL to fix

        Returns:
        -------
            str: Fixed url

        """
        if "mega.co.nz" in url:
            url: str = url.replace("mega.co.nz", "mega.nz")

        if "#F!" in url:
            return url.replace("#F!", "folder/").replace("!", "#")

        if "#!" in url:
            return url.replace("#!", "file/").replace("!", "#")

        return url


    def write_file(self, targetfile, newtext: str) -> None:
        """Automatically open, write, and save a URL to a file.

        Args:
        ----
            targetfile (file): File to be written to.
            newtext (str): String to write to file.

        """
        targetfile.seek(0,2)
        targetfile.write(f"{newtext}\n")
        targetfile.flush()
#=============================================================================================================
# Driver code
if (__name__ == "__main__"):
    if len(argv) == 1:
        print("No input file given. Exiting.")
        exit(1)
    else:
        checker: LinkChecker = LinkChecker(input_file=argv[1])
        checker.main()
