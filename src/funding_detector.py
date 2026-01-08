"""
Funding Detector for Venture Funding Monitor
Detects funding announcements in RSS articles using regex patterns.
Extracts company name, funding stage, amount, location, and industry.
"""

import logging
import re
from typing import Dict, Optional

from src import config

# Set up logging
logger = logging.getLogger(__name__)


class FundingDetector:
    """
    Detects and extracts funding announcement details from article text.

    Uses regex patterns to:
    1. Identify if an article is about funding
    2. Extract company name, stage, amount, location, industry
    3. Calculate relevance score based on your criteria

    Why regex instead of LLM?
    - Free (no API costs)
    - Fast (processes hundreds of articles quickly)
    - Deterministic (same input = same output)
    - Good enough for structured announcements in tech news
    """

    def analyze_article(self, article: Dict) -> Optional[Dict]:
        """
        Analyze an article to detect funding announcements.

        Args:
            article: Dictionary with 'title', 'description', 'url', 'source'

        Returns:
            Dictionary with extracted funding details and score,
            or None if not a funding announcement
        """
        # Combine title and description for full text analysis
        title = article.get('title', '')
        description = article.get('description', '')
        full_text = f"{title}. {description}"

        # Calculate relevance score
        score = self._calculate_score(full_text)

        # Only process if score meets threshold
        if score < config.RELEVANCE_THRESHOLD:
            logger.debug(f"Article below threshold (score: {score}): {title[:50]}")
            return None

        # Extract funding details
        company_name = self._extract_company_name(title)
        funding_stage = self._extract_funding_stage(full_text)
        funding_amount = self._extract_funding_amount(full_text)
        location = self._extract_location(full_text)
        industry = self._extract_industry(full_text)

        # Build result dictionary
        result = {
            'company_name': company_name or 'Unknown',
            'funding_stage': funding_stage or 'Unknown',
            'funding_amount': funding_amount or 'Not specified',
            'location': location or 'Unknown',
            'industry': industry or 'Tech',
            'description': description[:500],  # Limit length
            'relevance_score': score,
            'url': article.get('url', ''),
            'title': title,
            'source': article.get('source', '')
        }

        logger.info(f"Detected funding: {company_name} - {funding_stage} (score: {score})")
        return result

    def _calculate_score(self, text: str) -> int:
        """
        Calculate relevance score for an article (0-100).

        Scoring criteria (from plan):
        - Funding keywords: +30
        - Funding stage: +20
        - UK location: +30
        - Europe/Middle East location: +15
        - Fintech/SaaS industry: +20
        - Other tech: +10

        Args:
            text: Article title + description

        Returns:
            Score from 0-100
        """
        score = 0

        # 1. Check for funding keywords (+30)
        if config.FUNDING_KEYWORDS_PATTERN.search(text):
            score += config.SCORE_FUNDING_KEYWORDS

        # 2. Check for funding stage (+20)
        for stage, pattern in config.FUNDING_STAGES.items():
            if pattern.search(text):
                score += config.SCORE_FUNDING_STAGE
                break  # Only count once

        # 3. Check location (UK: +30, EU/ME: +15)
        if config.UK_KEYWORDS_PATTERN.search(text):
            score += config.SCORE_UK_LOCATION
        elif config.EU_KEYWORDS_PATTERN.search(text):
            score += config.SCORE_EU_LOCATION
        elif config.ME_KEYWORDS_PATTERN.search(text):
            score += config.SCORE_ME_LOCATION

        # 4. Check industry (priority: fintech/SaaS)
        if config.FINTECH_KEYWORDS_PATTERN.search(text):
            score += config.SCORE_FINTECH
        elif config.SAAS_KEYWORDS_PATTERN.search(text):
            score += config.SCORE_SAAS
        elif config.TECH_KEYWORDS_PATTERN.search(text):
            score += config.SCORE_TECH

        return min(score, 100)  # Cap at 100

    def _extract_company_name(self, title: str) -> Optional[str]:
        """
        Extract company name from article title.

        Tries multiple patterns in priority order:
        1. "CompanyName raises $X"
        2. "CompanyName, a [description], raises $X"
        3. "CompanyName has raised"

        Args:
            title: Article title

        Returns:
            Company name or None if not found
        """
        for pattern in config.COMPANY_NAME_PATTERNS:
            match = pattern.search(title)
            if match:
                company_name = match.group(1).strip()
                # Clean up common issues
                company_name = self._clean_company_name(company_name)
                logger.debug(f"Extracted company name: {company_name}")
                return company_name

        logger.debug(f"Could not extract company name from: {title}")
        return None

    def _clean_company_name(self, name: str) -> str:
        """
        Clean extracted company name.

        Removes trailing punctuation, extra spaces, etc.

        Args:
            name: Raw extracted name

        Returns:
            Cleaned company name
        """
        # Remove trailing punctuation
        name = name.rstrip('.,;:')
        # Remove extra spaces
        name = re.sub(r'\s+', ' ', name)
        return name.strip()

    def _extract_funding_stage(self, text: str) -> Optional[str]:
        """
        Extract funding stage (Seed, Series A/B/C).

        Args:
            text: Article text

        Returns:
            Funding stage or None if not found
        """
        for stage, pattern in config.FUNDING_STAGES.items():
            if pattern.search(text):
                logger.debug(f"Extracted funding stage: {stage}")
                return stage

        return None

    def _extract_funding_amount(self, text: str) -> Optional[str]:
        """
        Extract funding amount from text.

        Handles formats like:
        - $10M, £5m, €20B
        - $10 million, £5.5 million
        - 10 million dollars

        Args:
            text: Article text

        Returns:
            Funding amount string or None if not found
        """
        for pattern in config.AMOUNT_PATTERNS:
            match = pattern.search(text)
            if match:
                # Extract matched groups
                if len(match.groups()) == 2:
                    amount, unit = match.groups()
                    # Normalize unit
                    unit = unit.lower()
                    if unit.startswith('m'):
                        unit_normalized = 'million'
                    elif unit.startswith('b'):
                        unit_normalized = 'billion'
                    elif unit.startswith('k'):
                        unit_normalized = 'thousand'
                    else:
                        unit_normalized = unit

                    result = f"${amount}{unit_normalized[0].upper()}"  # e.g., "$10M"
                    logger.debug(f"Extracted funding amount: {result}")
                    return result

                elif len(match.groups()) == 3:
                    # Format: "10 million dollars"
                    amount, unit, currency = match.groups()
                    result = f"${amount}{unit[0].upper()}"  # e.g., "$10M"
                    logger.debug(f"Extracted funding amount: {result}")
                    return result

        return None

    def _extract_location(self, text: str) -> Optional[str]:
        """
        Extract geographic location from text.

        Priority: UK > Europe > Middle East

        Args:
            text: Article text

        Returns:
            Location string or None if not found
        """
        # Check UK first (highest priority)
        uk_match = config.UK_KEYWORDS_PATTERN.search(text)
        if uk_match:
            location = uk_match.group(0)
            logger.debug(f"Extracted location: {location} (UK)")
            return location

        # Check Europe
        eu_match = config.EU_KEYWORDS_PATTERN.search(text)
        if eu_match:
            location = eu_match.group(0)
            logger.debug(f"Extracted location: {location} (Europe)")
            return location

        # Check Middle East
        me_match = config.ME_KEYWORDS_PATTERN.search(text)
        if me_match:
            location = me_match.group(0)
            logger.debug(f"Extracted location: {location} (Middle East)")
            return location

        return None

    def _extract_industry(self, text: str) -> Optional[str]:
        """
        Extract industry/sector from text.

        Priority: Fintech > SaaS > Other Tech

        Args:
            text: Article text

        Returns:
            Industry string or None if not found
        """
        # Check fintech first (highest priority)
        if config.FINTECH_KEYWORDS_PATTERN.search(text):
            logger.debug("Extracted industry: Fintech")
            return "Fintech"

        # Check SaaS
        if config.SAAS_KEYWORDS_PATTERN.search(text):
            logger.debug("Extracted industry: SaaS")
            return "SaaS"

        # Check other tech
        tech_match = config.TECH_KEYWORDS_PATTERN.search(text)
        if tech_match:
            # Extract the specific tech keyword
            tech_type = tech_match.group(0)
            logger.debug(f"Extracted industry: {tech_type}")
            return tech_type.capitalize()

        return None


# Example usage and testing
if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test detector with sample articles
    detector = FundingDetector()

    # Test case 1: Clear funding announcement
    test_article_1 = {
        'title': 'London fintech startup Acme raises $10M Series A',
        'description': 'Acme, a London-based fintech company, has secured $10 million in Series A funding to expand its payment platform.',
        'url': 'https://example.com/article1',
        'source': 'TechCrunch'
    }

    print("Test Article 1:")
    print(f"Title: {test_article_1['title']}")
    result = detector.analyze_article(test_article_1)
    if result:
        print(f"✓ Detected funding announcement!")
        print(f"  Company: {result['company_name']}")
        print(f"  Stage: {result['funding_stage']}")
        print(f"  Amount: {result['funding_amount']}")
        print(f"  Location: {result['location']}")
        print(f"  Industry: {result['industry']}")
        print(f"  Score: {result['relevance_score']}")
    else:
        print("✗ Not detected as funding announcement")

    # Test case 2: Non-funding article
    print("\n" + "="*50 + "\n")
    test_article_2 = {
        'title': 'Apple releases new iPhone features',
        'description': 'Apple announced new features for the iPhone today, including improved camera capabilities.',
        'url': 'https://example.com/article2',
        'source': 'TechCrunch'
    }

    print("Test Article 2:")
    print(f"Title: {test_article_2['title']}")
    result = detector.analyze_article(test_article_2)
    if result:
        print(f"✓ Detected funding announcement (unexpected!)")
    else:
        print("✗ Correctly identified as non-funding article")

    # Test case 3: Middle East startup
    print("\n" + "="*50 + "\n")
    test_article_3 = {
        'title': 'Dubai-based SaaS company TechCorp secures $25M Series B',
        'description': 'TechCorp, a Dubai-based B2B software company, has closed a $25 million Series B round led by regional investors.',
        'url': 'https://example.com/article3',
        'source': 'VentureBeat'
    }

    print("Test Article 3:")
    print(f"Title: {test_article_3['title']}")
    result = detector.analyze_article(test_article_3)
    if result:
        print(f"✓ Detected funding announcement!")
        print(f"  Company: {result['company_name']}")
        print(f"  Stage: {result['funding_stage']}")
        print(f"  Amount: {result['funding_amount']}")
        print(f"  Location: {result['location']}")
        print(f"  Industry: {result['industry']}")
        print(f"  Score: {result['relevance_score']}")
    else:
        print("✗ Not detected as funding announcement")
