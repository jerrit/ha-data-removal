"""
opt_out_db.py — Opt-out data for 35 data broker sites.

This is the "source of truth" for:
  - Where each site is searched (search_url_template)
  - How to opt out (form URL, email, or mail)
  - Step-by-step instructions
  - Estimated processing time

These URLs were verified as of mid-2025. Data brokers occasionally move their
opt-out pages — if a URL stops working, update it here and re-run the seeder.

Adding a new site:
  1. Copy an existing entry from SITES (below)
  2. Fill in the fields — search_url_template is the most important one
  3. Restart the app — seed_sites() picks it up automatically
  4. Or use the "Add Site" form in the web dashboard (no code needed)

search_url_template placeholder reference:
  {first}       — USER_FIRST_NAME from .env
  {last}        — USER_LAST_NAME
  {city}        — USER_CITY (URL-encoded spaces → +)
  {state}       — USER_STATE (two-letter abbreviation)
  {state_full}  — USER_STATE_FULL
  {first_last}  — first-last (hyphenated, lowercase)
  {name}        — first+last (URL-encoded space)
"""

# ──────────────────────────────────────────────────────────────────────────── #
# The main lookup table. Import SITES elsewhere; call get_site_config(name)    #
# to retrieve a single entry by name.                                          #
# ──────────────────────────────────────────────────────────────────────────── #

SITES: list[dict] = [

    # ── 1. Whitepages ────────────────────────────────────────────────────── #
    {
        "name": "Whitepages",
        "url": "https://www.whitepages.com",
        "search_url_template": "https://www.whitepages.com/name/{first_last}/{state}",
        "opt_out_url": "https://www.whitepages.com/suppression-requests",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to whitepages.com/suppression-requests\n"
            "2. Search for your name and location\n"
            "3. Select your listing from the results\n"
            "4. Click 'Remove Me'\n"
            "5. Whitepages will call or text your listed phone number to verify\n"
            "6. Enter the verification code to complete removal\n"
            "Note: Phone number verification is REQUIRED — the bot cannot complete "
            "this step for you. Open the browser (HEADLESS=false) to watch and "
            "complete the phone verification yourself."
        ),
        "estimated_days": 1,
        "required_fields": ["first_name", "last_name", "state", "phone"],
    },

    # ── 2. Spokeo ────────────────────────────────────────────────────────── #
    {
        "name": "Spokeo",
        "url": "https://www.spokeo.com",
        "search_url_template": "https://www.spokeo.com/{first}-{last}/{state}",
        "opt_out_url": "https://www.spokeo.com/optout",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to spokeo.com/optout\n"
            "2. Paste the URL of your specific Spokeo listing (the bot copies this "
            "   from the scan step)\n"
            "3. Enter your email address\n"
            "4. Complete the CAPTCHA\n"
            "5. Click 'Opt Out'\n"
            "6. Check your email — Spokeo sends a confirmation link\n"
            "7. Click the link to finalise removal (usually takes 24–48 hours)"
        ),
        "estimated_days": 2,
        "required_fields": ["profile_url", "email"],
    },

    # ── 3. BeenVerified ──────────────────────────────────────────────────── #
    {
        "name": "BeenVerified",
        "url": "https://www.beenverified.com",
        "search_url_template": "https://www.beenverified.com/app/optout/search",
        "opt_out_url": "https://www.beenverified.com/app/optout/search",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to beenverified.com/app/optout/search\n"
            "2. Enter your first name, last name, and state\n"
            "3. Find your listing in the results and click 'Opt Out of This Record'\n"
            "4. Enter your email address\n"
            "5. Click 'Send Verification Email'\n"
            "6. Check your inbox and click the verification link\n"
            "Removal typically takes 24 hours after email verification."
        ),
        "estimated_days": 2,
        "required_fields": ["first_name", "last_name", "state", "email"],
    },

    # ── 4. MyLife ────────────────────────────────────────────────────────── #
    {
        "name": "MyLife",
        "url": "https://www.mylife.com",
        "search_url_template": "https://www.mylife.com/pub/search?search[name]={first}+{last}",
        "opt_out_url": "https://www.mylife.com/privacy/index.pubview",
        "opt_out_method": "email",
        "opt_out_instructions": (
            "MyLife requires a manual opt-out request via email.\n"
            "1. Send an email to: optout@mylife.com\n"
            "   Subject: 'Data Removal Request'\n"
            "   Body: Include your full name, city, state, and the URL of your "
            "   MyLife profile (found during the scan step)\n"
            "2. Alternatively use the CCPA/Privacy page at:\n"
            "   mylife.com/privacy/index.pubview\n"
            "3. MyLife typically processes requests within 30 days\n"
            "Note: The bot generates the email text for you — paste it into "
            "your email client and send it yourself."
        ),
        "estimated_days": 30,
        "required_fields": ["first_name", "last_name", "city", "state", "email", "profile_url"],
    },

    # ── 5. Intelius ──────────────────────────────────────────────────────── #
    {
        "name": "Intelius",
        "url": "https://www.intelius.com",
        "search_url_template": (
            "https://www.intelius.com/search/?search_type=person"
            "&qf={first}&qln={last}&qc={city}&qs={state}"
        ),
        "opt_out_url": "https://www.intelius.com/opt-out/submit/",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to intelius.com/opt-out/submit/\n"
            "2. Enter your first name, last name, city, and state\n"
            "3. Select your record from the search results\n"
            "4. Enter your email address and click 'Submit'\n"
            "5. Check your inbox for a confirmation email from Intelius\n"
            "6. Click the confirmation link to complete the opt-out\n"
            "Removal usually takes 72 hours after confirmation."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 6. PeopleFinder ──────────────────────────────────────────────────── #
    {
        "name": "PeopleFinder",
        "url": "https://www.peoplefinder.com",
        "search_url_template": (
            "https://www.peoplefinder.com/people-search/"
            "?fname={first}&lname={last}&state={state}"
        ),
        "opt_out_url": "https://www.peoplefinder.com/optout.php",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to peoplefinder.com/optout.php\n"
            "2. Enter the URL of your PeopleFinder listing\n"
            "3. Complete the CAPTCHA verification\n"
            "4. Click 'Opt Out'\n"
            "5. No email verification required — removal takes 24–48 hours\n"
            "Note: You need the exact profile URL from the scan step."
        ),
        "estimated_days": 2,
        "required_fields": ["profile_url"],
    },

    # ── 7. ZabaSearch ────────────────────────────────────────────────────── #
    {
        "name": "ZabaSearch",
        "url": "https://www.zabasearch.com",
        "search_url_template": "https://www.zabasearch.com/people/{first}+{last}/{state}/",
        "opt_out_url": "https://www.zabasearch.com/block_records/",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to zabasearch.com/block_records/\n"
            "2. Enter your first name, last name, city, and state\n"
            "3. Select your record from the results\n"
            "4. Enter your email address\n"
            "5. Click 'Block My Record'\n"
            "6. Confirm via the link in the verification email\n"
            "Removal typically takes 24–48 hours after email verification."
        ),
        "estimated_days": 2,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 8. FastPeopleSearch ──────────────────────────────────────────────── #
    {
        "name": "FastPeopleSearch",
        "url": "https://www.fastpeoplesearch.com",
        "search_url_template": "https://www.fastpeoplesearch.com/name/{first}-{last}_{state}",
        "opt_out_url": "https://www.fastpeoplesearch.com/removal",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to fastpeoplesearch.com/removal\n"
            "2. Paste your FastPeopleSearch profile URL (from the scan)\n"
            "3. Complete the CAPTCHA\n"
            "4. Click 'Remove My Info'\n"
            "5. Enter your email to confirm\n"
            "6. Click the link in the confirmation email\n"
            "FastPeopleSearch usually removes records within a few hours."
        ),
        "estimated_days": 1,
        "required_fields": ["profile_url", "email"],
    },

    # ── 9. TruthFinder ──────────────────────────────────────────────────── #
    {
        "name": "TruthFinder",
        "url": "https://www.truthfinder.com",
        "search_url_template": (
            "https://www.truthfinder.com/people-search/"
            "?firstName={first}&lastName={last}&state={state}&city={city}"
        ),
        "opt_out_url": "https://www.truthfinder.com/opt-out/",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to truthfinder.com/opt-out/\n"
            "2. Enter your first name, last name, city, and state\n"
            "3. Click 'Search'\n"
            "4. Find your record and click 'Remove Record'\n"
            "5. Enter your email address and submit\n"
            "6. Check your inbox for a TruthFinder verification email\n"
            "7. Click the link — removal takes 24–48 hours after that"
        ),
        "estimated_days": 2,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 10. Radaris ─────────────────────────────────────────────────────── #
    {
        "name": "Radaris",
        "url": "https://radaris.com",
        "search_url_template": "https://radaris.com/p/{first}/{last}/",
        "opt_out_url": "https://radaris.com/page/how-to-remove-information",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "Radaris has a multi-step removal process:\n"
            "1. Go to radaris.com and search for your name\n"
            "2. Find your profile and click the three-dot menu (⋯)\n"
            "3. Select 'Control Information'\n"
            "4. Create a free Radaris account (or log in)\n"
            "5. Claim your profile, then select 'Remove Profile'\n"
            "6. Confirm removal — takes up to 72 hours\n"
            "Alternative: Email privacy@radaris.com with your name, city, state, "
            "and a link to your profile.\n"
            "Note: Radaris requires account creation, which the bot cannot automate "
            "fully. Use HEADLESS=false to complete this step manually."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },
]

# ══════════════════════════════════════════════════════════════════════════════ #
# ADDITIONAL_SITES — 25 more data brokers                                        #
# These use the generic scanner (no hand-written Playwright code needed).        #
# Add new sites here — or via the web dashboard — and they'll be picked up       #
# automatically on the next scan.                                                 #
# ══════════════════════════════════════════════════════════════════════════════ #

ADDITIONAL_SITES: list[dict] = [

    # ── 11. Instant Checkmate ────────────────────────────────────────────── #
    {
        "name": "Instant Checkmate",
        "url": "https://www.instantcheckmate.com",
        "search_url_template": "https://www.instantcheckmate.com/people/{first_last}/",
        "opt_out_url": "https://www.instantcheckmate.com/opt-out/",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to instantcheckmate.com/opt-out/\n"
            "2. Search for your name and state\n"
            "3. Select your record and click 'Remove This Record'\n"
            "4. Enter your email address and submit\n"
            "5. Click the confirmation link in the email Instant Checkmate sends\n"
            "Removal typically takes 24–72 hours."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "state", "email"],
    },

    # ── 12. That's Them ──────────────────────────────────────────────────── #
    {
        "name": "ThatsThem",
        "url": "https://thatsthem.com",
        "search_url_template": "https://thatsthem.com/name/{first}/{last}/{state}",
        "opt_out_url": "https://thatsthem.com/optout",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to thatsthem.com/optout\n"
            "2. Enter your name and email address\n"
            "3. Click 'Opt Out'\n"
            "4. Check your email for a verification link from That's Them\n"
            "5. Click the link to complete the opt-out\n"
            "Removal is usually processed within 24 hours."
        ),
        "estimated_days": 1,
        "required_fields": ["first_name", "last_name", "email"],
    },

    # ── 13. Nuwber ───────────────────────────────────────────────────────── #
    {
        "name": "Nuwber",
        "url": "https://nuwber.com",
        "search_url_template": (
            "https://nuwber.com/search?name={first}+{last}&location={city}%2C+{state}"
        ),
        "opt_out_url": "https://nuwber.com/removal",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to nuwber.com/removal\n"
            "2. Search for your name and location\n"
            "3. Select your listing\n"
            "4. Enter your email and submit the removal request\n"
            "5. Verify via the email Nuwber sends you\n"
            "Removal usually takes 24–48 hours."
        ),
        "estimated_days": 2,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 14. CheckPeople ──────────────────────────────────────────────────── #
    {
        "name": "CheckPeople",
        "url": "https://checkpeople.com",
        "search_url_template": (
            "https://checkpeople.com/search?fname={first}&lname={last}&state={state}"
        ),
        "opt_out_url": "https://checkpeople.com/opt-out",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to checkpeople.com/opt-out\n"
            "2. Enter your first name, last name, city, and state\n"
            "3. Find your record and click 'Opt Out'\n"
            "4. Provide your email address for verification\n"
            "5. Click the confirmation link in the email\n"
            "Removal takes 24–48 hours."
        ),
        "estimated_days": 2,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 15. CocoFinder ───────────────────────────────────────────────────── #
    {
        "name": "CocoFinder",
        "url": "https://cocofinder.com",
        "search_url_template": (
            "https://cocofinder.com/people?fname={first}&lname={last}&state={state}"
        ),
        "opt_out_url": "https://cocofinder.com/opt-out",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to cocofinder.com/opt-out\n"
            "2. Search for your name and state\n"
            "3. Select your record and click 'Remove My Info'\n"
            "4. Enter your email and submit\n"
            "5. Confirm via email link\n"
            "Removal typically takes 24 hours."
        ),
        "estimated_days": 1,
        "required_fields": ["first_name", "last_name", "state", "email"],
    },

    # ── 16. SearchPeopleFree ─────────────────────────────────────────────── #
    {
        "name": "SearchPeopleFree",
        "url": "https://www.searchpeoplefree.com",
        "search_url_template": "https://www.searchpeoplefree.com/find/{first}-{last}/{state}",
        "opt_out_url": "https://www.searchpeoplefree.com/opt-out",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to searchpeoplefree.com/opt-out\n"
            "2. Paste the URL of your specific SearchPeopleFree listing\n"
            "3. Enter your email and submit\n"
            "4. Confirm via the verification email\n"
            "Removal takes 24–48 hours."
        ),
        "estimated_days": 2,
        "required_fields": ["profile_url", "email"],
    },

    # ── 17. USPhoneBook ──────────────────────────────────────────────────── #
    {
        "name": "USPhoneBook",
        "url": "https://www.usphonebook.com",
        "search_url_template": "https://www.usphonebook.com/{first}+{last}/{state}",
        "opt_out_url": "https://www.usphonebook.com/opt-out",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to usphonebook.com/opt-out\n"
            "2. Enter your name and email\n"
            "3. Click 'Remove My Info'\n"
            "4. Confirm via the verification email\n"
            "Removal takes 24–72 hours."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "email"],
    },

    # ── 18. FamilyTreeNow ────────────────────────────────────────────────── #
    {
        "name": "FamilyTreeNow",
        "url": "https://www.familytreenow.com",
        "search_url_template": (
            "https://www.familytreenow.com/search/genealogy/results"
            "?qfn={first}&qln={last}&qls={state}"
        ),
        "opt_out_url": "https://www.familytreenow.com/optout",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to familytreenow.com/optout\n"
            "2. Search for your name\n"
            "3. Click on your record and then 'Opt Out of This Record'\n"
            "4. Enter your email and submit\n"
            "5. Check email for verification link\n"
            "Removal takes up to 48 hours."
        ),
        "estimated_days": 2,
        "required_fields": ["first_name", "last_name", "email"],
    },

    # ── 19. PeopleSmart ──────────────────────────────────────────────────── #
    # Part of the Intelius network — opting out of Intelius covers this too,
    # but a direct opt-out here is faster.
    {
        "name": "PeopleSmart",
        "url": "https://www.peoplesmart.com",
        "search_url_template": (
            "https://www.peoplesmart.com/people-search/results"
            "?FirstName={first}&LastName={last}&CityName={city}&StateName={state}"
        ),
        "opt_out_url": "https://www.peoplesmart.com/manage/optout",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "PeopleSmart is part of the Intelius network.\n"
            "1. Go to peoplesmart.com/manage/optout\n"
            "2. Enter your first name, last name, city, and state\n"
            "3. Select your record and click 'Opt Out'\n"
            "4. Enter your email and submit\n"
            "5. Click the verification link in the email\n"
            "Note: Opting out of Intelius (site #5) should also cover PeopleSmart."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 20. CyberBackgroundChecks ────────────────────────────────────────── #
    {
        "name": "CyberBackgroundChecks",
        "url": "https://www.cyberbackgroundchecks.com",
        "search_url_template": (
            "https://www.cyberbackgroundchecks.com/people/{first}-{last}/{state}"
        ),
        "opt_out_url": "https://www.cyberbackgroundchecks.com/removal",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to cyberbackgroundchecks.com/removal\n"
            "2. Enter your name and city/state\n"
            "3. Click 'Search' and find your record\n"
            "4. Click 'Remove Record'\n"
            "5. Complete the CAPTCHA and submit\n"
            "No email verification required. Takes 24–48 hours."
        ),
        "estimated_days": 2,
        "required_fields": ["first_name", "last_name", "city", "state"],
    },

    # ── 21. GoLookUp ─────────────────────────────────────────────────────── #
    {
        "name": "GoLookUp",
        "url": "https://golookup.com",
        "search_url_template": (
            "https://golookup.com/people-search/search-results"
            "?firstName={first}&lastName={last}&state={state}"
        ),
        "opt_out_url": "https://golookup.com/privacyremoval",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to golookup.com/privacyremoval\n"
            "2. Search for your name and select your record\n"
            "3. Click 'Submit Opt-Out Request'\n"
            "4. Enter your email and submit\n"
            "5. Click the verification link in the email\n"
            "Removal takes 2–5 business days."
        ),
        "estimated_days": 5,
        "required_fields": ["first_name", "last_name", "state", "email"],
    },

    # ── 22. InfoTracer ───────────────────────────────────────────────────── #
    {
        "name": "InfoTracer",
        "url": "https://www.infotracer.com",
        "search_url_template": (
            "https://www.infotracer.com/people/search"
            "?firstname={first}&lastname={last}&state={state}"
        ),
        "opt_out_url": "https://www.infotracer.com/optout",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to infotracer.com/optout\n"
            "2. Enter your name, city, and state\n"
            "3. Find and select your record\n"
            "4. Enter your email and submit the removal request\n"
            "5. Verify via the email link\n"
            "Removal takes 48–72 hours."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 23. PublicRecordsNow ─────────────────────────────────────────────── #
    {
        "name": "PublicRecordsNow",
        "url": "https://www.publicrecordsnow.com",
        "search_url_template": (
            "https://www.publicrecordsnow.com/find/person"
            "?firstName={first}&lastName={last}&state={state}"
        ),
        "opt_out_url": "https://www.publicrecordsnow.com/static/view/opt-out",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to publicrecordsnow.com/static/view/opt-out\n"
            "2. Enter your full name, city, and state\n"
            "3. Select your record from the results\n"
            "4. Enter your email and submit\n"
            "5. Confirm via email link\n"
            "Removal takes 24–48 hours."
        ),
        "estimated_days": 2,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 24. AnyWho ───────────────────────────────────────────────────────── #
    # AnyWho is part of the Intelius network.
    {
        "name": "AnyWho",
        "url": "https://www.anywho.com",
        "search_url_template": "https://www.anywho.com/people/{first}+{last}/{state}",
        "opt_out_url": "https://www.anywho.com/opt-out",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "AnyWho is operated by the Intelius network.\n"
            "1. Go to anywho.com/opt-out\n"
            "2. Enter your name, city, and state\n"
            "3. Select your listing and click 'Remove'\n"
            "4. Enter your email and submit\n"
            "5. Verify via email\n"
            "Note: Opting out of Intelius (site #5) should also cover AnyWho."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 25. 411.com ──────────────────────────────────────────────────────── #
    {
        "name": "411.com",
        "url": "https://www.411.com",
        "search_url_template": "https://www.411.com/name/{first}_{last}/{state}",
        "opt_out_url": "https://www.411.com/privacy/request",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to 411.com/privacy/request\n"
            "2. Select 'I want to opt out of a listing'\n"
            "3. Enter your first name, last name, city, and state\n"
            "4. Select your listing from the results\n"
            "5. Submit the removal form\n"
            "Removal typically takes 3–5 business days."
        ),
        "estimated_days": 5,
        "required_fields": ["first_name", "last_name", "city", "state"],
    },

    # ── 26. PeopleFinders ────────────────────────────────────────────────── #
    # (different from PeopleFinder.com — note the 's')
    {
        "name": "PeopleFinders",
        "url": "https://www.peoplefinders.com",
        "search_url_template": "https://www.peoplefinders.com/people/{first}-{last}/{state}",
        "opt_out_url": "https://www.peoplefinders.com/manage/optout",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to peoplefinders.com/manage/optout\n"
            "2. Enter your first name, last name, city, and state\n"
            "3. Locate your record and click 'Remove My Record'\n"
            "4. Enter your email and submit\n"
            "5. Click the verification link in the email from PeopleFinders\n"
            "Removal usually completes within 24 hours."
        ),
        "estimated_days": 1,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 27. Xlek ─────────────────────────────────────────────────────────── #
    {
        "name": "Xlek",
        "url": "https://xlek.com",
        "search_url_template": (
            "https://xlek.com/search?name={first}+{last}&location={city}%2C+{state}"
        ),
        "opt_out_url": "https://xlek.com/optout",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to xlek.com/optout\n"
            "2. Enter your name and email address\n"
            "3. Describe the listing you want removed (include name and city/state)\n"
            "4. Submit the form\n"
            "Xlek processes opt-outs within a few days."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 28. VoterRecords ─────────────────────────────────────────────────── #
    {
        "name": "VoterRecords",
        "url": "https://voterrecords.com",
        "search_url_template": "https://voterrecords.com/voters/{first}+{last}/{state}",
        "opt_out_url": "https://voterrecords.com/faq",
        "opt_out_method": "email",
        "opt_out_instructions": (
            "VoterRecords requires a manual email opt-out.\n"
            "1. Email: privacy@voterrecords.com\n"
            "   Subject: 'Opt-Out Request'\n"
            "   Body: Include your full name, city, state, and the URL of your listing\n"
            "2. They are legally required to respond within 30 days\n"
            "The bot will generate the email text for you."
        ),
        "estimated_days": 30,
        "required_fields": ["first_name", "last_name", "city", "state", "email", "profile_url"],
    },

    # ── 29. IDTrue ───────────────────────────────────────────────────────── #
    {
        "name": "IDTrue",
        "url": "https://www.idtrue.com",
        "search_url_template": (
            "https://www.idtrue.com/search/person/"
            "?firstName={first}&lastName={last}&state={state}"
        ),
        "opt_out_url": "https://www.idtrue.com/opt-out",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to idtrue.com/opt-out\n"
            "2. Find your record by searching your name and state\n"
            "3. Click the opt-out link next to your record\n"
            "4. Enter your email and submit\n"
            "5. Verify via email confirmation link\n"
            "Removal takes 24–48 hours."
        ),
        "estimated_days": 2,
        "required_fields": ["first_name", "last_name", "state", "email"],
    },

    # ── 30. PrivateEye ───────────────────────────────────────────────────── #
    # Part of the Intelius network.
    {
        "name": "PrivateEye",
        "url": "https://www.privateeye.com",
        "search_url_template": (
            "https://www.privateeye.com/find/person"
            "?fname={first}&lname={last}&state={state}"
        ),
        "opt_out_url": "https://www.privateeye.com/optout",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "PrivateEye is operated by the Intelius network.\n"
            "1. Go to privateeye.com/optout\n"
            "2. Enter your first name, last name, city, and state\n"
            "3. Select your record and click 'Opt Out'\n"
            "4. Enter your email and submit\n"
            "5. Verify via the email link\n"
            "Note: Opting out of Intelius (site #5) should also cover PrivateEye."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 31. PublicSeek ───────────────────────────────────────────────────── #
    {
        "name": "PublicSeek",
        "url": "https://publicseek.com",
        "search_url_template": (
            "https://publicseek.com/people/{first}+{last}/{state}"
        ),
        "opt_out_url": "https://publicseek.com/remove",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to publicseek.com/remove\n"
            "2. Enter your name and email address\n"
            "3. Describe the record to remove (name, city, state)\n"
            "4. Submit — no email verification needed\n"
            "Removal typically takes 24–72 hours."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 32. Addresses.com ────────────────────────────────────────────────── #
    # Part of the Intelius network.
    {
        "name": "Addresses.com",
        "url": "https://www.addresses.com",
        "search_url_template": "https://www.addresses.com/people/{first}+{last}/{state}/",
        "opt_out_url": "https://www.addresses.com/optout.php",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "Addresses.com is operated by the Intelius network.\n"
            "1. Go to addresses.com/optout.php\n"
            "2. Enter your first name, last name, city, and state\n"
            "3. Select your record and click 'Remove'\n"
            "4. Enter your email and submit\n"
            "5. Verify via email\n"
            "Note: Opting out of Intelius (site #5) should also cover this site."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 33. US Search ────────────────────────────────────────────────────── #
    # Part of the Intelius network.
    {
        "name": "US Search",
        "url": "https://www.ussearch.com",
        "search_url_template": (
            "https://www.ussearch.com/search/pub/results/"
            "?firstName={first}&lastName={last}&state={state}"
        ),
        "opt_out_url": "https://www.ussearch.com/manage/optout",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "US Search is part of the Intelius network.\n"
            "1. Go to ussearch.com/manage/optout\n"
            "2. Enter your name, city, and state\n"
            "3. Select your record and click 'Opt Out'\n"
            "4. Enter your email and submit\n"
            "5. Verify via email confirmation\n"
            "Note: Opting out of Intelius (site #5) should also cover US Search."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },

    # ── 34. Verispy ──────────────────────────────────────────────────────── #
    {
        "name": "Verispy",
        "url": "https://www.verispy.com",
        "search_url_template": (
            "https://www.verispy.com/people/search"
            "?firstname={first}&lastname={last}&state={state}"
        ),
        "opt_out_url": "https://www.verispy.com/people/opt-out",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "1. Go to verispy.com/people/opt-out\n"
            "2. Search for your name and state\n"
            "3. Find your record and click 'Remove Record'\n"
            "4. Enter your email address and submit\n"
            "5. Check your inbox for the Verispy verification email\n"
            "Removal usually takes 48 hours."
        ),
        "estimated_days": 2,
        "required_fields": ["first_name", "last_name", "state", "email"],
    },

    # ── 35. PeopleLookup ─────────────────────────────────────────────────── #
    # Part of the Intelius network.
    {
        "name": "PeopleLookup",
        "url": "https://www.peoplelookup.com",
        "search_url_template": (
            "https://www.peoplelookup.com/results/first={first}&last={last}"
            "&state={state}&city={city}/"
        ),
        "opt_out_url": "https://www.peoplelookup.com/manage/optout",
        "opt_out_method": "form",
        "opt_out_instructions": (
            "PeopleLookup is operated by the Intelius network.\n"
            "1. Go to peoplelookup.com/manage/optout\n"
            "2. Enter your first name, last name, city, and state\n"
            "3. Find your record and click 'Opt Out'\n"
            "4. Enter your email and submit\n"
            "5. Click the verification link in the email\n"
            "Note: Opting out of Intelius (site #5) should also cover PeopleLookup."
        ),
        "estimated_days": 3,
        "required_fields": ["first_name", "last_name", "city", "state", "email"],
    },
]

# ── Combined list used everywhere ────────────────────────────────────────── #
# Import ALL_SITES (not SITES) to get the full 35-site list.
ALL_SITES = SITES + ADDITIONAL_SITES


def get_site_config(name: str) -> dict | None:
    """Look up a site by name (case-insensitive). Returns None if not found."""
    name_lower = name.lower()
    for site in ALL_SITES:
        if site["name"].lower() == name_lower:
            return site
    return None


def get_all_site_names() -> list[str]:
    return [s["name"] for s in ALL_SITES]
