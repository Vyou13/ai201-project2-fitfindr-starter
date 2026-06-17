# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock dataset (`listings.json`) using case-insensitive keyword matching against title, description, and style tags, while strictly filtering by size and a maximum price boundary.

**Input parameters:**

<!-- List each parameter, its type, and what it represents -->

- `description` (str): The search query or item keywords provided by the user (e.g., "vintage graphic tee").
- `size` (str): Optional size filter string (e.g., "M", "L"). If `None` or `"Any"`, size filtering is skipped.
- `max_price` (float): Optional upper price limit. If `None`, price filtering is skipped.

**What it returns:**
Returns a `list` of dictionaries, where each dictionary represents a matching marketplace item with the following fields: `id` (int), `title` (str), `description` (str), `category` (str), `style_tags` (list), `size` (str), `condition` (str), `price` (float), `colors` (list), `brand` (str), and `platform` (str). The list is sorted by relevance (keyword-match score) in descending order, so the best match is first.

**What happens if it fails or returns nothing:**
If no matches are found, the tool returns an empty list `[]`. It must not throw an exception. The agent's planning loop will detect this empty list, populate a user-friendly error message suggesting looser search constraints, and terminate the session early without calling downstream tools.

---

### Tool 2: suggest_outfit

**What it does:**
<Uses the Groq LLM API (`llama-3.3-70b-versatile`) to generate a highly cohesive, 3-to-4 sentence fashion styling suggestion matching a newly discovered item with pieces from the user's current wardrobe.

**Input parameters:**

- `new_item` (dict): The dictionary containing metadata for the top-matched thrift listing from Step 1.
- `wardrobe` (dict): A dictionary matching the structured wardrobe schema containing an `items` key (a list of clothing items owned by the user).

**What it returns:**
Returns a `str` containing concrete, encouraging styling advice detailing item proportions, color interactions, and specific styling notes (e.g., "tuck the front corner", "cuff the hems once").

**What happens if it fails or returns nothing:**

If the `wardrobe` dictionary is empty or contains no items, the tool activates a fallback styling prompt. This prompt instructs the LLM to assume an empty closet and build a complete outfit suggestion using standard, universal fashion staples (e.g., classic white tees, straight-leg denim, minimalist white sneakers) instead of crashing or returning an error.

---

### Tool 3: create_fit_card

**What it does:**

Generates a brief, punchy, all-lowercase social media caption embedded with 1-2 relevant emojis, specifically optimized for platforms like Instagram Stories or TikTok.

**Input parameters:**

<!-- List each parameter, its type, and what it represents -->

- `outfit` (...): The text-based styling suggestion produced by `suggest_outfit`.

**What it returns:**

Returns a unique `str` representing a high-vibe social media caption. It uses a high LLM temperature setting ($\ge 0.8$) to guarantee distinct outputs on identical inputs across separate invocations.

**What happens if it fails or returns nothing:**
An inline string-guard validates the incoming `outfit` text. If the input is empty or contains only whitespace, the tool returns a descriptive error string: `"Error: Cannot generate a fit card caption without a valid outfit description."` This prevents making unnecessary API calls to Groq or outputting corrupted text blocks to the user interface.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

The agent implements an explicit, state-checked conditional loop inside `run_agent()` that evaluates execution results step-by-step:

**Query parsing (Step 2):** The free-text query is parsed deterministically with regex + token matching (no LLM call), keeping parsing fast, predictable, and easy to test. A regex extracts `max_price` from patterns like `$30`, `under 30`, `below 25.50`, or `max 40`; `size` is pulled from `size <X>` or a standalone size token (XS/S/M/L/XL...); the remaining words, minus price/size mentions and filler stopwords, become the `description`. The result is stored in `session["parsed"]`.

1. Initialize a clean session dictionary with keys set to `None`.
2. Invoke `search_listings`. Check if the returned list is empty.
   - **Branch A (Error Path)**: If empty, set a helpful recommendation string under `session["error"]` and **return early**, bypassing all remaining tools.
   - **Branch B (Happy Path)**: If populated, assign the item at index `0` to `session["selected_item"]` and advance.
3. Invoke `suggest_outfit` using `session["selected_item"]` and the current wardrobe dictionary. Store the generated string in `session["outfit_suggestion"]`. If an unexpected API error is caught, write it to `session["error"]` and halt.
4. Invoke `create_fit_card` using `session["outfit_suggestion"]` and `session["selected_item"]`. Save the final text to `session["fit_card"]`.
5. Return the finalized session state to the application handler.

---

## State Management

**How does information from one tool get passed to the next?**
State is centralized and managed within a unified execution dictionary object (`session`) across the duration of the request:

```python
session = {
    "selected_item": None,
    "outfit_suggestion": None,
    "fit_card": None,
    "error": None
}

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool            | Failure mode                          | Agent response |
| --------------- | ------------------------------------- | -------------- |
| search_listings | No results match the query            | Returns []. The planning loop catches this, populates session["error"] with an alternative suggestion (e.g., "Try expanding your budget or adjusting keywords"), and stops execution early.               |
| suggest_outfit  | Wardrobe is empty                     |  Detects the empty structure and injects an alternate system prompt instructing the LLM to design an outfit utilizing universal capsule wardrobe staples (e.g., white tees, jeans).              |
| create_fit_card | Outfit input is missing or incomplete | Intercepts the request with an inline check (if not outfit.strip()) and immediately returns a clean, human-readable error string instead of calling the LLM API or crashing the app.               |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->
     graph TD
    User([User Request Input]) --> PL{Planning Loop Brain}

    %% Tool 1 Execution
    PL -->|1. Parse Parameters| T1[search_listings]
    T1 -->|Empty Array Result []| E1[Set Session Error & Halt Early]
    E1 -->|Exit Loop Early| End([Render UI View])
    T1 -->|Valid Items Found| S1[Set session: selected_item = results[0]]

    %% Tool 2 Execution
    S1 -->|2. Ingest Item Data| T2[suggest_outfit]
    T2 -->|Empty Wardrobe State| FA[Apply Baseline Staple Fallback Prompts]
    T2 -->|Populated Wardrobe State| CO[Weave Wardrobe Items with New Item]
    FA --> S2[Set session: outfit_suggestion]
    CO --> S2

    %% Tool 3 Execution
    S2 -->|3. Format Text Context| T3[create_fit_card]
    T3 -->|Empty Outfit Text Guard| E2[Set Session Error String]
    T3 -->|Valid Text Input| S3[Set session: fit_card caption]

    E2 --> End
    S3 --> End
---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
AI Tool: Claude 3.5 Sonnet / Copilot.

Input Context: Tool 1, Tool 2, and Tool 3 specifications blocks from this planning.md file (defining exact parameters, expected return formats, and fallback rules).

Expected Production: Clean, standalone Python functions inside tools.py using load_listings() and the standard Groq API client syntax.

Verification Method: I will inspect the code to ensure case-insensitivity on search and explicit handling of empty inputs. Then, I will write and execute an isolated suite using pytest tests/test_tools.py to assert that happy paths and failure conditions yield predictable results.

**Milestone 4 — Planning loop and state management:**
AI Tool: Claude 3.5 Sonnet / ChatGPT.

Input Context: The complete Mermaid flowchart architecture diagram and the Planning Loop & State Management text sections from this planning.md.

Expected Production: A robust orchestration function run_agent() inside agent.py managing the session dictionary.

Verification Method: I will explicitly check that an early return statement trips when a search yields zero items. I will verify it by printing out the resulting session object using a test script execution (python agent.py).
---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**

The planning loop initializes an empty session state. It calls search_listings(description="vintage graphic tee", size="M", max_price=30.0). The tool loads listings.json, finds matching items, sorts them by price, and returns the top hit: a "Faded Band Tee" listed for $22 on Depop in Good condition. The loop stores this item under session["selected_item"].

**Step 2:**

The planning loop checks that session["selected_item"] is valid. It automatically routes this dictionary data alongside the user's selected wardrobe array directly into suggest_outfit(). The tool triggers a Groq API completion, processing the item details against the user's baggy jeans and chunky sneakers preference. It returns a paragraph outlining a cohesive outfit configuration, which is saved to session["outfit_suggestion"].

**Step 3:**

The planning loop passes session["outfit_suggestion"] and the original metadata from session["selected_item"] directly into create_fit_card(). Groq processes the text at a high temperature setting, rendering a short, engaging, all-lowercase caption complete with emojis. This value is recorded in session["fit_card"].

**Final output to user:**

The Gradio UI panel updates all three boxes seamlessly for the user:Listing,Outfit Suggestion and Fit Card Caption
```
