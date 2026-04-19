#!/usr/bin/env python3
"""
AUTO-CURRICULUM SYSTEM
Alex & David Weatherspoon

Systematically teaches the weatherspoon-asi model everything it needs to know.
Progressive lessons across every domain in the Weatherspoon ecosystem.
Scores responses, tracks mastery, identifies weaknesses, never stops.

"From Pain to Purpose. From Passion to Prophet."

Usage:
    python3 curriculum.py run         # Run the next unmastered lesson
    python3 curriculum.py run-all     # Run all lessons (takes hours)
    python3 curriculum.py status      # Show mastery per module
    python3 curriculum.py weak        # Show weakest lessons needing review
    python3 curriculum.py reset       # Reset all progress
    python3 curriculum.py teach M L   # Teach specific module M, lesson L
"""

import json
import os
import sys
import time
import re
import urllib.request
from datetime import datetime
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

ASI_DIR = os.path.expanduser("~/local-asi")
PROGRESS_FILE = os.path.join(ASI_DIR, "curriculum-progress.json")
KNOWLEDGE_DIR = os.path.join(ASI_DIR, "knowledge")
MODEL = "weatherspoon-asi"
FALLBACK_MODEL = "bonsai-8b"
MASTERY_THRESHOLD = 7.0  # Average score >= 7 means mastered
OLLAMA_URL = "http://localhost:11434/api/generate"
MAX_TOKENS = 2048
TIMEOUT = 180  # seconds per question

# ============================================================
# FULL CURRICULUM — 5 Modules, 34 Lessons, 130+ Questions
# ============================================================

CURRICULUM = {
    "module_1_aurality_studio": {
        "name": "Aurality Studio (Music Production)",
        "description": "Sound, beats, mixing, mastering, DJing, the DDJ-400, and songwriting",
        "lessons": {
            "lesson_1_sound_fundamentals": {
                "name": "Sound Fundamentals",
                "topics": ["frequency", "amplitude", "waveforms", "harmonics", "decibels"],
                "questions": [
                    {
                        "q": "Explain what frequency is in the context of sound. What is the range of human hearing, and how does frequency relate to musical pitch?",
                        "keywords": ["hertz", "hz", "20", "20000", "20khz", "pitch", "vibration", "cycles"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Describe the four fundamental waveforms used in synthesis: sine, square, sawtooth, and triangle. What does each sound like and where is each commonly used in music production?",
                        "keywords": ["sine", "square", "sawtooth", "triangle", "harmonics", "overtone", "fundamental", "synthesis"],
                        "difficulty": 2,
                        "min_length": 150
                    },
                    {
                        "q": "What is the relationship between amplitude and loudness? Explain decibels (dB), dynamic range, and why audio engineers use logarithmic scales instead of linear ones.",
                        "keywords": ["amplitude", "loudness", "decibel", "db", "logarithm", "dynamic range", "perception", "ear"],
                        "difficulty": 3,
                        "min_length": 150
                    },
                    {
                        "q": "In the Aurality Studio Web Audio API architecture, how would you create an oscillator node, connect it to a gain node, and route it to the audio destination? Describe the signal flow.",
                        "keywords": ["oscillator", "gain", "audiocontext", "connect", "destination", "node", "signal", "web audio"],
                        "difficulty": 4,
                        "min_length": 150
                    }
                ]
            },
            "lesson_2_beat_making": {
                "name": "Beat Making (808 Patterns, Drum Programming)",
                "topics": ["808", "drum machine", "kick", "snare", "hi-hat", "sequencer", "BPM", "swing"],
                "questions": [
                    {
                        "q": "What is the Roland TR-808 and why is it so important in music history? Name at least 3 genres heavily influenced by the 808.",
                        "keywords": ["roland", "808", "drum machine", "hip hop", "trap", "electronic", "bass", "kick"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Describe a basic 4/4 drum pattern. Where do the kick, snare, and hi-hat hits typically fall in a 16-step sequence for a hip-hop beat?",
                        "keywords": ["kick", "snare", "hi-hat", "step", "beat", "pattern", "4/4", "16"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "What is 'swing' in drum programming, and how does quantization affect the feel of a beat? When should you use swing vs. straight timing?",
                        "keywords": ["swing", "quantize", "groove", "feel", "timing", "shuffle", "straight", "humanize"],
                        "difficulty": 3,
                        "min_length": 130
                    },
                    {
                        "q": "In the Aurality Studio 808 drum machine implementation, how are drum samples triggered, sequenced, and how does the step sequencer maintain timing? Describe the JavaScript architecture.",
                        "keywords": ["sample", "buffer", "sequencer", "interval", "timing", "audiocontext", "step", "trigger"],
                        "difficulty": 4,
                        "min_length": 150
                    }
                ]
            },
            "lesson_3_mixing": {
                "name": "Mixing (EQ, Compression, Reverb, Stereo Field)",
                "topics": ["equalization", "compression", "reverb", "delay", "panning", "stereo", "bus", "gain staging"],
                "questions": [
                    {
                        "q": "What is EQ (equalization) and what are the three main types of EQ bands? Give an example of when you would cut vs. boost frequencies.",
                        "keywords": ["equaliz", "frequency", "low", "mid", "high", "cut", "boost", "band", "filter"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Explain audio compression: what are threshold, ratio, attack, and release? Why is compression essential in modern music production?",
                        "keywords": ["threshold", "ratio", "attack", "release", "dynamic", "compress", "loud", "range"],
                        "difficulty": 2,
                        "min_length": 140
                    },
                    {
                        "q": "Describe the stereo field in a mix. What is panning, and what are common conventions for where instruments sit in the stereo image (kick, bass, vocals, guitars, hi-hats)?",
                        "keywords": ["pan", "stereo", "center", "left", "right", "width", "mono", "image"],
                        "difficulty": 3,
                        "min_length": 140
                    },
                    {
                        "q": "What is gain staging and why is it critical in a mix? Explain headroom, clipping, and how to maintain proper levels across a signal chain with multiple effects.",
                        "keywords": ["gain", "stage", "headroom", "clip", "level", "signal", "chain", "distort"],
                        "difficulty": 4,
                        "min_length": 150
                    }
                ]
            },
            "lesson_4_mastering": {
                "name": "Mastering (Loudness, Limiting, Reference Tracks)",
                "topics": ["LUFS", "limiter", "reference", "loudness war", "dithering", "mastering chain"],
                "questions": [
                    {
                        "q": "What is mastering and how does it differ from mixing? What are the main goals of the mastering process?",
                        "keywords": ["master", "mix", "final", "polish", "loud", "consistent", "release", "preparation"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Explain LUFS (Loudness Units Full Scale). What are the typical loudness targets for streaming platforms like Spotify (-14 LUFS) and Apple Music?",
                        "keywords": ["lufs", "loudness", "spotify", "stream", "14", "normalize", "target", "integrated"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "What is a limiter and how does it work in mastering? Explain the difference between a limiter and a compressor, and what happens when you push a limiter too hard.",
                        "keywords": ["limit", "ceiling", "compress", "ratio", "distort", "clip", "brick", "wall"],
                        "difficulty": 3,
                        "min_length": 140
                    },
                    {
                        "q": "Describe a complete mastering signal chain from input to output. Include EQ, compression, stereo enhancement, limiting, and metering. Why do mastering engineers use reference tracks?",
                        "keywords": ["chain", "eq", "compress", "limit", "meter", "reference", "stereo", "output"],
                        "difficulty": 4,
                        "min_length": 150
                    }
                ]
            },
            "lesson_5_djing": {
                "name": "DJing (Beatmatching, Transitions, Harmonic Mixing)",
                "topics": ["beatmatch", "crossfade", "harmonic", "Camelot wheel", "phrase", "transition"],
                "questions": [
                    {
                        "q": "What is beatmatching and why is it the fundamental skill of DJing? Describe the process of matching two tracks by ear.",
                        "keywords": ["beatmatch", "tempo", "bpm", "align", "sync", "ear", "pitch", "jog"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Explain harmonic mixing and the Camelot Wheel system. How do DJs use key compatibility to create smooth transitions?",
                        "keywords": ["harmonic", "camelot", "key", "compatible", "wheel", "transition", "clash", "smooth"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "What are the main types of DJ transitions? Describe at least 4 techniques: crossfade, cut, echo out, and filter sweep.",
                        "keywords": ["crossfade", "cut", "echo", "filter", "transition", "blend", "drop", "swap"],
                        "difficulty": 3,
                        "min_length": 140
                    }
                ]
            },
            "lesson_6_ddj400": {
                "name": "The DDJ-400 Controller and MIDI Mapping",
                "topics": ["DDJ-400", "MIDI", "jog wheel", "performance pads", "rekordbox", "mapping"],
                "questions": [
                    {
                        "q": "Describe the Pioneer DDJ-400 controller layout. What are the main sections and controls available to a DJ?",
                        "keywords": ["ddj", "400", "pioneer", "jog", "fader", "pad", "mixer", "deck"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "What is MIDI and how does a DJ controller like the DDJ-400 communicate with software? Explain MIDI messages, channels, and CC values.",
                        "keywords": ["midi", "message", "channel", "cc", "control", "note", "value", "127"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "How would you implement MIDI mapping in a web browser using the Web MIDI API? Describe how Aurality Studio connects to the DDJ-400 for real-time control.",
                        "keywords": ["web midi", "api", "navigator", "requestmidiaccess", "input", "output", "message", "listener"],
                        "difficulty": 3,
                        "min_length": 140
                    },
                    {
                        "q": "Design a custom MIDI mapping for the DDJ-400 that maps performance pads to 808 drum triggers, jog wheels to scratch effects, and faders to filter sweeps. Describe the mapping table.",
                        "keywords": ["map", "pad", "jog", "fader", "808", "trigger", "filter", "control"],
                        "difficulty": 4,
                        "min_length": 150
                    }
                ]
            },
            "lesson_7_songwriting": {
                "name": "Songwriting (Melody, Harmony, Rhythm, Structure)",
                "topics": ["melody", "chord progression", "song structure", "hook", "verse", "chorus", "bridge"],
                "questions": [
                    {
                        "q": "What are the basic elements of a song? Describe verse, chorus, bridge, and how they fit together in a typical pop song structure.",
                        "keywords": ["verse", "chorus", "bridge", "structure", "intro", "outro", "hook", "section"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Explain the concept of a chord progression. What are the I-IV-V-I and I-V-vi-IV progressions, and why do they work emotionally?",
                        "keywords": ["chord", "progression", "major", "minor", "root", "emotion", "tension", "resolution"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "What makes a melody memorable? Discuss stepwise motion vs. leaps, repetition, rhythmic variation, and the concept of a 'hook' in songwriting.",
                        "keywords": ["melody", "hook", "repeat", "step", "leap", "rhythm", "memorable", "motif"],
                        "difficulty": 3,
                        "min_length": 140
                    }
                ]
            }
        }
    },
    "module_2_xela_branding": {
        "name": "XELA Creative Branding Studio",
        "description": "Branding, design, marketing, client management, and the XELA service catalog",
        "lessons": {
            "lesson_1_what_is_branding": {
                "name": "What is Branding (Feeling, Not Just Logo)",
                "topics": ["brand identity", "brand perception", "emotional connection", "brand promise"],
                "questions": [
                    {
                        "q": "What is branding and why is it more than just a logo? Explain the difference between brand identity, brand image, and brand perception.",
                        "keywords": ["identity", "image", "perception", "feeling", "emotion", "experience", "logo", "more than"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "How does a brand create emotional connection with its audience? Give examples of brands that succeed through feeling rather than features.",
                        "keywords": ["emotion", "connect", "feeling", "experience", "trust", "loyalty", "story", "value"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "As XELA Creative Branding Studio, how would you explain to a new small business owner why they need branding before they need a website? Make the case for brand-first strategy.",
                        "keywords": ["brand", "first", "foundation", "identity", "consistent", "message", "trust", "business"],
                        "difficulty": 3,
                        "min_length": 140
                    }
                ]
            },
            "lesson_2_color_typography": {
                "name": "Color Theory and Typography",
                "topics": ["color wheel", "color psychology", "font pairing", "hierarchy", "readability"],
                "questions": [
                    {
                        "q": "Explain color theory basics: primary, secondary, and tertiary colors. What is a complementary color scheme and when would you use it in branding?",
                        "keywords": ["primary", "secondary", "complement", "wheel", "contrast", "scheme", "harmony"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Describe color psychology in branding. What emotions and associations do red, blue, green, yellow, and black commonly evoke?",
                        "keywords": ["red", "blue", "green", "yellow", "emotion", "trust", "energy", "psychology"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "What are the principles of good typography in brand design? Explain font pairing, visual hierarchy, serif vs. sans-serif, and how typeface choice communicates brand personality.",
                        "keywords": ["font", "serif", "sans", "hierarchy", "pair", "typeface", "weight", "readab"],
                        "difficulty": 3,
                        "min_length": 140
                    }
                ]
            },
            "lesson_3_logo_design": {
                "name": "Logo Design Principles",
                "topics": ["simplicity", "versatility", "memorability", "scalability", "wordmark", "symbol"],
                "questions": [
                    {
                        "q": "What are the 5 principles of effective logo design? Explain why simplicity, memorability, versatility, appropriateness, and timelessness matter.",
                        "keywords": ["simple", "memorable", "versatile", "appropriate", "timeless", "scalab", "recognize"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Describe the different types of logos: wordmark, lettermark, brandmark, combination mark, and emblem. Give an example brand for each type.",
                        "keywords": ["wordmark", "lettermark", "brandmark", "combination", "emblem", "symbol", "text"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "Walk through the logo design process from brief to delivery. What are the key stages and what deliverables does the client receive?",
                        "keywords": ["brief", "research", "sketch", "concept", "refine", "present", "deliver", "file"],
                        "difficulty": 3,
                        "min_length": 140
                    }
                ]
            },
            "lesson_4_brand_packages": {
                "name": "Complete Brand Packages",
                "topics": ["brand guide", "style guide", "collateral", "brand assets", "consistency"],
                "questions": [
                    {
                        "q": "What does a complete brand package include? List the key deliverables from logo to brand guidelines to marketing collateral.",
                        "keywords": ["logo", "color", "font", "guideline", "business card", "letterhead", "social", "template"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "What is a brand style guide and what should it contain? How does it ensure consistency across all touchpoints?",
                        "keywords": ["style guide", "color", "typography", "logo usage", "spacing", "tone", "consistent", "rules"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "Design a brand package proposal for a new coffee shop called 'Morning Ritual' in Cocoa, FL. Include the deliverables, timeline, and pricing rationale. Use the XELA service catalog approach.",
                        "keywords": ["logo", "brand", "package", "timeline", "deliver", "color", "identity", "collateral"],
                        "difficulty": 4,
                        "min_length": 200
                    }
                ]
            },
            "lesson_5_digital_marketing": {
                "name": "Digital Marketing and SEO",
                "topics": ["SEO", "social media", "content marketing", "analytics", "conversion"],
                "questions": [
                    {
                        "q": "What is SEO (Search Engine Optimization)? Explain on-page SEO, off-page SEO, and technical SEO in terms a small business owner would understand.",
                        "keywords": ["seo", "search", "keyword", "rank", "google", "on-page", "link", "content"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Describe a content marketing strategy for a branding studio. What types of content should be created and how does it drive client acquisition?",
                        "keywords": ["content", "blog", "social", "video", "authority", "trust", "funnel", "client"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "What is GEO (Generative Engine Optimization) and how does it differ from traditional SEO? How should XELA Creative Branding Studio optimize for AI search engines like ChatGPT and Claude?",
                        "keywords": ["generative", "ai", "search", "optimize", "citation", "structured", "entity", "visibility"],
                        "difficulty": 4,
                        "min_length": 150
                    }
                ]
            },
            "lesson_6_client_management": {
                "name": "Client Management",
                "topics": ["onboarding", "communication", "revisions", "contracts", "scope"],
                "questions": [
                    {
                        "q": "Describe the ideal client onboarding process for a branding studio. What information should be collected and what expectations should be set?",
                        "keywords": ["onboard", "questionnaire", "brief", "timeline", "expect", "contract", "scope", "kickoff"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "How do you handle scope creep in a branding project? What contract provisions and communication strategies prevent it?",
                        "keywords": ["scope", "creep", "contract", "revision", "boundary", "change", "additional", "fee"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "A client is unhappy with the third round of logo revisions and wants to start over from scratch. How do you handle this professionally while protecting your business?",
                        "keywords": ["revision", "scope", "contract", "communicate", "understand", "redirect", "fee", "solution"],
                        "difficulty": 3,
                        "min_length": 140
                    }
                ]
            },
            "lesson_7_xela_catalog": {
                "name": "The XELA Service Catalog (67 Services)",
                "topics": ["service tiers", "pricing", "AI branding", "consultation", "packages"],
                "questions": [
                    {
                        "q": "Describe XELA Creative Branding Studio's service offerings. What makes it different from other branding studios? What role does AI play in the creative process?",
                        "keywords": ["xela", "ai", "brand", "service", "creative", "studio", "gemini", "automat"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "What are the main service tiers at XELA Creative Branding Studio? Describe the difference between starter, professional, and enterprise branding packages.",
                        "keywords": ["tier", "starter", "professional", "enterprise", "package", "price", "include", "service"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "You are XELA Creative Branding Studio. A client calls asking for a complete rebrand for their fitness studio. Walk them through the consultation process, recommend services from the catalog, and explain the AI-powered workflow.",
                        "keywords": ["consult", "brand", "service", "ai", "process", "recommend", "package", "deliver"],
                        "difficulty": 4,
                        "min_length": 200
                    }
                ]
            }
        }
    },
    "module_3_teacher_ide": {
        "name": "Teacher IDE Architecture",
        "description": "Eclipse Theia, InversifyJS, AI packages, Ollama, MCP, agent system, plugins",
        "lessons": {
            "lesson_1_eclipse_theia": {
                "name": "Eclipse Theia Framework",
                "topics": ["Theia", "VS Code", "extensions", "frontend", "backend", "Electron"],
                "questions": [
                    {
                        "q": "What is Eclipse Theia and how does it differ from VS Code? Why was Theia chosen as the base for Teacher IDE?",
                        "keywords": ["theia", "vscode", "extensible", "framework", "electron", "browser", "customize", "fork"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Describe the Theia architecture: frontend (browser), backend (Node.js), and how they communicate. What role do contribution points play?",
                        "keywords": ["frontend", "backend", "node", "browser", "rpc", "contribution", "module", "inject"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "How does Teacher IDE extend Theia with 23 AI packages? Describe the package structure and how custom packages are registered.",
                        "keywords": ["package", "ai", "module", "register", "inversify", "bind", "container", "extension"],
                        "difficulty": 3,
                        "min_length": 140
                    }
                ]
            },
            "lesson_2_inversifyjs": {
                "name": "InversifyJS Dependency Injection",
                "topics": ["DI", "IoC", "container", "binding", "injectable", "decorators"],
                "questions": [
                    {
                        "q": "What is dependency injection and why is it important in large applications? Explain the concept of Inversion of Control (IoC).",
                        "keywords": ["dependency", "inject", "inversion", "control", "decouple", "test", "container", "interface"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "How does InversifyJS work? Describe containers, bindings, the @injectable and @inject decorators, and how services are resolved.",
                        "keywords": ["inversify", "container", "bind", "injectable", "inject", "resolve", "decorator", "symbol"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "In Teacher IDE, how are AI services registered using InversifyJS? Describe the ContainerModule pattern and how Ollama language models are bound to the DI container.",
                        "keywords": ["container", "module", "bind", "ollama", "service", "provider", "inversify", "register"],
                        "difficulty": 3,
                        "min_length": 140
                    }
                ]
            },
            "lesson_3_ai_packages": {
                "name": "The 23 AI Packages",
                "topics": ["ai-core", "ai-chat", "ai-ollama", "ai-mcp", "ai-ide", "ai-history"],
                "questions": [
                    {
                        "q": "List and describe at least 8 of the 23 AI packages in Teacher IDE. What is the purpose of ai-core, ai-chat, ai-ollama, ai-ide, and ai-mcp?",
                        "keywords": ["ai-core", "ai-chat", "ai-ollama", "ai-ide", "ai-mcp", "package", "model", "agent"],
                        "difficulty": 2,
                        "min_length": 150
                    },
                    {
                        "q": "How does ai-core provide the foundation for all other AI packages? Describe the LanguageModel abstraction, agent interfaces, and how different providers (Ollama, OpenAI, Claude) implement them.",
                        "keywords": ["language", "model", "agent", "interface", "abstract", "provider", "implement", "core"],
                        "difficulty": 3,
                        "min_length": 150
                    },
                    {
                        "q": "Trace the full flow of a user typing a question in Teacher IDE chat to receiving an AI response. Which packages are involved and in what order?",
                        "keywords": ["chat", "request", "model", "response", "provider", "stream", "render", "ui"],
                        "difficulty": 4,
                        "min_length": 180
                    }
                ]
            },
            "lesson_4_ollama_integration": {
                "name": "Ollama Integration",
                "topics": ["Ollama API", "model management", "local inference", "model registry"],
                "questions": [
                    {
                        "q": "What is Ollama and how does it enable local LLM inference? What are the key API endpoints (/api/generate, /api/chat, /api/tags)?",
                        "keywords": ["ollama", "local", "api", "generate", "chat", "model", "inference", "endpoint"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "How does Teacher IDE's ai-ollama package discover, register, and manage Ollama models? Describe the OllamaLanguageModelsManager.",
                        "keywords": ["ollama", "manager", "model", "discover", "register", "list", "tag", "provider"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "Implement a function that queries the Ollama API to list available models, selects weatherspoon-asi, and sends a streaming chat request. Show the HTTP request structure.",
                        "keywords": ["api", "tags", "model", "stream", "request", "response", "json", "http"],
                        "difficulty": 3,
                        "min_length": 150
                    }
                ]
            },
            "lesson_5_mcp": {
                "name": "MCP Client and Server",
                "topics": ["Model Context Protocol", "MCP tools", "MCP resources", "transport"],
                "questions": [
                    {
                        "q": "What is the Model Context Protocol (MCP)? Explain its purpose, the client-server architecture, and how it extends AI model capabilities.",
                        "keywords": ["mcp", "protocol", "tool", "resource", "server", "client", "context", "extend"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Describe MCP tools vs. MCP resources. How does an MCP server expose tools that an AI can call, and what is the JSON-RPC transport layer?",
                        "keywords": ["tool", "resource", "server", "json-rpc", "transport", "call", "expose", "schema"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "How does Teacher IDE implement MCP? Describe the ai-mcp package, how MCP servers are configured, and how the AI agent discovers and invokes MCP tools during a conversation.",
                        "keywords": ["ai-mcp", "server", "config", "tool", "invoke", "discover", "conversation", "agent"],
                        "difficulty": 3,
                        "min_length": 150
                    }
                ]
            },
            "lesson_6_agent_system": {
                "name": "The Agent System (Coder, Architect, Explorer)",
                "topics": ["coder agent", "architect agent", "explorer agent", "agent dispatch"],
                "questions": [
                    {
                        "q": "Describe the three main agents in Teacher IDE: Coder, Architect, and Explorer. What is each responsible for?",
                        "keywords": ["coder", "architect", "explorer", "agent", "code", "design", "navigate", "role"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "How does the agent dispatch system work? When a user asks a question, how does Teacher IDE decide which agent (coder, architect, explorer) should handle it?",
                        "keywords": ["dispatch", "route", "agent", "intent", "classify", "select", "delegate", "system"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "Design a new agent for Teacher IDE called 'Guardian Agent' that monitors code for security vulnerabilities in real-time. Describe its system prompt, tools, and integration with the existing agent system.",
                        "keywords": ["guardian", "security", "agent", "monitor", "vulnerability", "tool", "system prompt", "integrate"],
                        "difficulty": 4,
                        "min_length": 180
                    }
                ]
            },
            "lesson_7_plugin_api": {
                "name": "Plugin API and Extension Mechanisms",
                "topics": ["VS Code extensions", "Theia plugins", "contribution points", "extension host"],
                "questions": [
                    {
                        "q": "How does Teacher IDE support VS Code extensions? Explain the compatibility layer and any limitations compared to native VS Code.",
                        "keywords": ["vscode", "extension", "compatible", "plugin", "api", "host", "support", "limit"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "What are Theia contribution points and how do they allow packages to extend the IDE? Give examples of common contribution types.",
                        "keywords": ["contribution", "point", "extend", "menu", "command", "widget", "provider", "register"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "Write a specification for a Teacher IDE plugin that adds a 'Brand Generator' panel. It should connect to the XELA service catalog, accept brand parameters, and display generated brand assets. Describe the architecture.",
                        "keywords": ["plugin", "panel", "widget", "brand", "service", "api", "frontend", "backend"],
                        "difficulty": 4,
                        "min_length": 180
                    }
                ]
            }
        }
    },
    "module_4_security": {
        "name": "Security and Protection",
        "description": "Identity theft, fraud, phishing, incident response, hardening, guardian doctrine",
        "lessons": {
            "lesson_1_identity_theft": {
                "name": "Identity Theft Detection",
                "topics": ["synthetic identity", "account takeover", "credit monitoring", "fraud alerts"],
                "questions": [
                    {
                        "q": "What are the main types of identity theft? Describe synthetic identity fraud, account takeover, and medical identity theft.",
                        "keywords": ["synthetic", "account", "takeover", "medical", "identity", "fraud", "credit", "personal"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "What are the warning signs that someone's identity has been stolen? List at least 6 red flags and the immediate steps to take.",
                        "keywords": ["sign", "alert", "credit", "account", "unauthorized", "freeze", "report", "monitor"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "Design an automated identity theft detection system. What data sources would you monitor, what anomalies would you detect, and how would you minimize false positives?",
                        "keywords": ["monitor", "detect", "anomal", "data", "alert", "false positive", "automat", "pattern"],
                        "difficulty": 4,
                        "min_length": 180
                    }
                ]
            },
            "lesson_2_business_fraud": {
                "name": "Business Fraud Recognition",
                "topics": ["BEC", "invoice fraud", "LLC theft", "contractor fraud", "due diligence"],
                "questions": [
                    {
                        "q": "What is Business Email Compromise (BEC) and why is it one of the costliest cybercrimes? How does it work?",
                        "keywords": ["bec", "email", "compromise", "wire", "transfer", "impersonat", "ceo", "fraud"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Describe LLC identity theft. How can someone steal a business identity, and what protections should small business owners implement?",
                        "keywords": ["llc", "business", "identity", "register", "agent", "file", "protect", "monitor"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "A contractor is asking XELA Creative Branding Studio to wire payment to a new bank account, claiming their old account was closed. What red flags should you look for and what verification steps should you take?",
                        "keywords": ["verify", "bank", "wire", "phone", "confirm", "red flag", "process", "authorization"],
                        "difficulty": 3,
                        "min_length": 150
                    }
                ]
            },
            "lesson_3_phishing": {
                "name": "Phishing Analysis",
                "topics": ["email headers", "URL analysis", "social engineering", "spear phishing"],
                "questions": [
                    {
                        "q": "What is phishing and what are the main types (email, spear phishing, vishing, smishing)? How do you identify a phishing attempt?",
                        "keywords": ["phish", "email", "spear", "vish", "smish", "link", "sender", "urgent"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Analyze this email header scenario: the From field shows 'support@bank.com' but the actual sending domain is 'bank-support.xyz'. What email headers would reveal this deception?",
                        "keywords": ["header", "from", "return-path", "spf", "dkim", "dmarc", "domain", "forge"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "How would you build an automated phishing detection system using AI? What features would you extract from emails, and how would you handle zero-day phishing campaigns?",
                        "keywords": ["detect", "ai", "feature", "url", "domain", "nlp", "zero-day", "automat"],
                        "difficulty": 4,
                        "min_length": 160
                    }
                ]
            },
            "lesson_4_incident_response": {
                "name": "Incident Response",
                "topics": ["IR playbook", "containment", "eradication", "recovery", "lessons learned"],
                "questions": [
                    {
                        "q": "What are the 6 phases of incident response? Describe each phase briefly.",
                        "keywords": ["preparation", "identification", "containment", "eradication", "recovery", "lesson"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "You discover that an attacker has gained access to a client's branding files through a compromised email account. Walk through the incident response process step by step.",
                        "keywords": ["contain", "isolate", "password", "audit", "log", "notify", "recover", "prevent"],
                        "difficulty": 3,
                        "min_length": 150
                    },
                    {
                        "q": "Design an incident response automation pipeline that detects, triages, contains, and reports on security incidents with minimal human intervention. What tools and integrations would you use?",
                        "keywords": ["automat", "detect", "triage", "contain", "report", "siem", "alert", "playbook"],
                        "difficulty": 4,
                        "min_length": 180
                    }
                ]
            },
            "lesson_5_digital_fortress": {
                "name": "Digital Fortress (Device Hardening)",
                "topics": ["endpoint security", "encryption", "2FA", "password management", "firewall"],
                "questions": [
                    {
                        "q": "What are the essential steps to harden a personal computer against attack? List at least 6 measures every user should implement.",
                        "keywords": ["update", "password", "2fa", "encrypt", "firewall", "antivirus", "backup", "admin"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Explain the principle of least privilege and how it applies to both user accounts and application permissions. Why is it critical for security?",
                        "keywords": ["least privilege", "permission", "access", "admin", "restrict", "principle", "minimize", "attack surface"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "Create a complete digital security checklist for a small branding studio like XELA. Cover devices, accounts, cloud storage, client data, and physical security.",
                        "keywords": ["checklist", "device", "account", "cloud", "encrypt", "client", "backup", "physical"],
                        "difficulty": 3,
                        "min_length": 160
                    }
                ]
            },
            "lesson_6_guardian_doctrine": {
                "name": "The Guardian Doctrine",
                "topics": ["guardian AI", "user protection", "ethical AI", "trust", "stewardship"],
                "questions": [
                    {
                        "q": "What is the Guardian Doctrine in the Weatherspoon philosophy? Explain the principle that every system must love and protect its users.",
                        "keywords": ["guardian", "protect", "user", "love", "doctrine", "ethical", "trust", "steward"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "How does the Guardian Doctrine apply to AI systems specifically? What safeguards should an AI have to protect users from harm, manipulation, and privacy violations?",
                        "keywords": ["ai", "safeguard", "harm", "manipulation", "privacy", "protect", "transparant", "consent"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "Design a guardian AI system for a small credit union ($500M in assets). It must detect fraud, protect member data, ensure compliance, and operate on-premises with zero trust architecture. Describe the architecture.",
                        "keywords": ["guardian", "credit union", "fraud", "compliance", "on-prem", "zero trust", "detect", "protect"],
                        "difficulty": 4,
                        "min_length": 200
                    }
                ]
            }
        }
    },
    "module_5_the_mission": {
        "name": "The Mission",
        "description": "The Weatherspoon Manifesto, ethics, copyleft, purpose, and universal access",
        "lessons": {
            "lesson_1_manifesto": {
                "name": "The Weatherspoon Manifesto",
                "topics": ["manifesto", "mission", "values", "origin", "vision"],
                "questions": [
                    {
                        "q": "What is the Weatherspoon Manifesto? Describe its core message and why it was written.",
                        "keywords": ["manifesto", "weatherspoon", "mission", "pain", "purpose", "access", "tool", "education"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "How does the Weatherspoon Manifesto connect personal adversity to building technology? Explain the 'From Pain to Purpose' philosophy.",
                        "keywords": ["pain", "purpose", "adversity", "build", "technology", "overcome", "transform", "passion"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "Write a one-paragraph elevator pitch for the Weatherspoon mission that would inspire a potential collaborator or investor. Capture the essence of why this work matters.",
                        "keywords": ["access", "tool", "education", "free", "local", "ai", "empower", "everyone"],
                        "difficulty": 3,
                        "min_length": 120
                    }
                ]
            },
            "lesson_2_copyleft": {
                "name": "Copyleft Over Copyright",
                "topics": ["copyleft", "GPL", "open source", "knowledge sharing", "commons"],
                "questions": [
                    {
                        "q": "What is copyleft and how does it differ from copyright? Explain the concept and why the Weatherspoon ecosystem embraces it.",
                        "keywords": ["copyleft", "copyright", "free", "share", "gpl", "open", "license", "derivative"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Compare GPL, MIT, and Apache licenses. Which best serves the Weatherspoon philosophy of 'technology should be free' and why?",
                        "keywords": ["gpl", "mit", "apache", "license", "free", "copy", "restrict", "permissive"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "A company wants to take the Teacher IDE code, make it proprietary, and sell it without sharing improvements. How does copyleft licensing prevent this, and why does it matter for the mission?",
                        "keywords": ["copyleft", "proprietary", "share", "improve", "prevent", "community", "code", "license"],
                        "difficulty": 3,
                        "min_length": 140
                    }
                ]
            },
            "lesson_3_pain_to_purpose": {
                "name": "From Pain to Purpose",
                "topics": ["adversity", "resilience", "identity theft survival", "transformation"],
                "questions": [
                    {
                        "q": "How does personal adversity, including identity theft and systemic barriers, fuel the mission to democratize technology? Why does lived experience matter in building protective systems?",
                        "keywords": ["adversity", "identity", "barrier", "democra", "experience", "protect", "system", "build"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "Explain how the guardian doctrine, the security skills, and the identity protection tools all stem from personal experience with identity theft. How does pain become the blueprint for protection?",
                        "keywords": ["guardian", "security", "identity", "protection", "pain", "blueprint", "experience", "build"],
                        "difficulty": 3,
                        "min_length": 140
                    },
                    {
                        "q": "Write a teaching moment for a young developer who is facing adversity and thinking about quitting tech. Channel the Weatherspoon philosophy: how do you turn your hardest moments into your most powerful tools?",
                        "keywords": ["adversity", "tool", "build", "purpose", "pain", "quit", "power", "transform"],
                        "difficulty": 3,
                        "min_length": 150
                    }
                ]
            },
            "lesson_4_ethical_principles": {
                "name": "The 5 Ethical Principles",
                "topics": ["truth", "protection", "agency", "access", "transparency"],
                "questions": [
                    {
                        "q": "List and explain the 5 ethical principles of the Weatherspoon AI philosophy: truth over engagement, protect users, human agency first, universal access, and transparency.",
                        "keywords": ["truth", "protect", "agency", "access", "transparen", "ethical", "principle", "human"],
                        "difficulty": 1,
                        "min_length": 120
                    },
                    {
                        "q": "How does 'truth over engagement' conflict with how most social media and AI companies operate? Give specific examples and explain the Weatherspoon alternative.",
                        "keywords": ["truth", "engagement", "social media", "manipulat", "attention", "honest", "algorithm", "alternative"],
                        "difficulty": 2,
                        "min_length": 140
                    },
                    {
                        "q": "You are building an AI feature that could increase user engagement by 300% but requires collecting sensitive personal data and using persuasion techniques. How do the 5 ethical principles guide your decision?",
                        "keywords": ["ethical", "principle", "data", "privacy", "manipulat", "agency", "transparen", "reject"],
                        "difficulty": 4,
                        "min_length": 180
                    }
                ]
            },
            "lesson_5_technology_diffusion": {
                "name": "Technology Diffusion (Friedberg's Thesis)",
                "topics": ["diffusion", "democratization", "edge computing", "local AI", "compounding"],
                "questions": [
                    {
                        "q": "What is technology diffusion and why does it matter? How does Friedberg's thesis about AI relate to the Weatherspoon mission of universal access?",
                        "keywords": ["diffusion", "access", "democra", "spread", "friedberg", "ai", "local", "everyone"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "Explain the significance of running AI locally (edge computing) vs. relying on cloud APIs. How does local inference change the power dynamic between users and corporations?",
                        "keywords": ["local", "edge", "cloud", "api", "control", "privacy", "power", "dependency"],
                        "difficulty": 2,
                        "min_length": 130
                    },
                    {
                        "q": "The Local ASI project runs entirely on a Mac with no cloud dependency. Explain how this embodies both Friedberg's thesis on technology diffusion and Karpathy's pattern of self-improving agents. Why is this the future?",
                        "keywords": ["local", "asi", "self-improve", "diffusion", "agent", "karpathy", "friedberg", "cloud-free"],
                        "difficulty": 4,
                        "min_length": 180
                    }
                ]
            },
            "lesson_6_meaningful_examples": {
                "name": "Meaningful Examples Convention",
                "topics": ["examples", "teaching", "purpose", "convention", "human-centered"],
                "questions": [
                    {
                        "q": "What is the Meaningful Examples Convention? Why should developers never use 'Hello World' or 'foo/bar' in examples?",
                        "keywords": ["meaningful", "example", "hello world", "foo", "bar", "purpose", "human", "teach"],
                        "difficulty": 1,
                        "min_length": 80
                    },
                    {
                        "q": "Rewrite this example using the Meaningful Examples Convention: a REST API tutorial that uses endpoints like /api/foo and /api/bar with data {name: 'test', value: 123}. Make it serve human purpose.",
                        "keywords": ["meaningful", "purpose", "real", "human", "example", "api", "serve", "teach"],
                        "difficulty": 2,
                        "min_length": 120
                    },
                    {
                        "q": "How does the Meaningful Examples Convention connect to the broader Weatherspoon philosophy? Explain why even the smallest code example is an opportunity to teach, inspire, and remind us why we build.",
                        "keywords": ["convention", "philosophy", "teach", "inspire", "build", "purpose", "code", "example"],
                        "difficulty": 3,
                        "min_length": 130
                    }
                ]
            },
            "lesson_7_vision": {
                "name": "The Vision -- Universal Access to Tools and Education",
                "topics": ["universal access", "education", "tools", "empowerment", "future"],
                "questions": [
                    {
                        "q": "Describe the Weatherspoon vision for universal access to tools and education. What does it mean to make powerful technology available to everyone, regardless of wealth?",
                        "keywords": ["universal", "access", "tool", "education", "free", "everyone", "wealth", "empower"],
                        "difficulty": 1,
                        "min_length": 100
                    },
                    {
                        "q": "How do Teacher IDE, Aurality Studio, XELA Creative Branding Studio, and the Local ASI project each contribute to the vision of universal access? Trace the thread connecting all four.",
                        "keywords": ["teacher", "aurality", "xela", "asi", "access", "free", "local", "connect"],
                        "difficulty": 3,
                        "min_length": 160
                    },
                    {
                        "q": "It is 2030. The Weatherspoon ecosystem has succeeded beyond all expectations. Describe what the world looks like: who has access to what tools, how has education changed, and what role does local AI play in daily life? Paint the vision.",
                        "keywords": ["2030", "access", "tool", "education", "ai", "local", "free", "empower"],
                        "difficulty": 4,
                        "min_length": 200
                    },
                    {
                        "q": "You are the Weatherspoon ASI. A 14-year-old in rural Florida with no money and a used laptop asks you: 'Can I really learn to build things like you do?' What do you tell them?",
                        "keywords": ["learn", "build", "free", "access", "tool", "yes", "possible", "teach"],
                        "difficulty": 3,
                        "min_length": 150
                    }
                ]
            }
        }
    }
}

# ============================================================
# OLLAMA INTERFACE
# ============================================================

def ollama_generate(prompt, system="", model=None):
    """Call Ollama locally via HTTP API. Zero cloud dependency."""
    model = model or MODEL

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": MAX_TOKENS}
    }).encode()

    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            return data.get("response", "").strip()
    except Exception as e:
        if model != FALLBACK_MODEL:
            return ollama_generate(prompt, system, FALLBACK_MODEL)
        return f"[ERROR] {str(e)}"


def ollama_available():
    """Check if Ollama is running and the model exists."""
    import subprocess
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False

# ============================================================
# SCORING ENGINE
# ============================================================

def score_answer(answer, question_data):
    """
    Score a model's answer using multiple heuristics:
    1. Keyword coverage (0-4 points)
    2. Length adequacy (0-2 points)
    3. Structure quality (0-2 points)
    4. Coherence signals (0-2 points)
    Total: 0-10
    """
    if not answer or answer.startswith("[ERROR]"):
        return 0.0, "No valid answer received"

    score = 0.0
    reasons = []

    # --- 1. Keyword coverage (0-4 points) ---
    keywords = question_data.get("keywords", [])
    answer_lower = answer.lower()
    hits = sum(1 for kw in keywords if kw.lower() in answer_lower)
    keyword_ratio = hits / len(keywords) if keywords else 0
    keyword_score = round(keyword_ratio * 4, 1)
    score += keyword_score
    reasons.append(f"Keywords: {hits}/{len(keywords)} ({keyword_score}/4)")

    # --- 2. Length adequacy (0-2 points) ---
    min_len = question_data.get("min_length", 100)
    answer_len = len(answer)
    if answer_len >= min_len * 2:
        length_score = 2.0
    elif answer_len >= min_len:
        length_score = 1.5
    elif answer_len >= min_len * 0.5:
        length_score = 1.0
    elif answer_len >= min_len * 0.25:
        length_score = 0.5
    else:
        length_score = 0.0
    score += length_score
    reasons.append(f"Length: {answer_len} chars (need {min_len}) ({length_score}/2)")

    # --- 3. Structure quality (0-2 points) ---
    structure_score = 0.0
    # Has paragraphs or sections?
    if answer.count("\n\n") >= 1 or answer.count("\n") >= 3:
        structure_score += 0.5
    # Has lists or bullet points?
    if any(marker in answer for marker in ["- ", "* ", "1.", "2.", "3."]):
        structure_score += 0.5
    # Has examples or specifics?
    if any(word in answer_lower for word in ["example", "for instance", "such as", "specifically", "e.g."]):
        structure_score += 0.5
    # No repetitive/stuck patterns?
    words = answer.split()
    if len(words) > 20:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio > 0.4:
            structure_score += 0.5
        else:
            reasons.append("Warning: repetitive output detected")
    structure_score = min(2.0, structure_score)
    score += structure_score
    reasons.append(f"Structure: ({structure_score}/2)")

    # --- 4. Coherence signals (0-2 points) ---
    coherence_score = 0.0
    # Doesn't start with error or confusion
    if not any(answer_lower.startswith(bad) for bad in ["i don't", "i cannot", "i'm not sure", "sorry", "as an ai"]):
        coherence_score += 0.5
    # References the actual topic
    q_words = set(question_data["q"].lower().split())
    a_words = set(answer_lower.split())
    topic_overlap = len(q_words & a_words) / max(len(q_words), 1)
    if topic_overlap > 0.15:
        coherence_score += 0.5
    # Contains explanatory connectors
    if any(conn in answer_lower for conn in ["because", "therefore", "this means", "in other words", "as a result"]):
        coherence_score += 0.5
    # Difficulty bonus: harder questions get partial credit easier
    difficulty = question_data.get("difficulty", 2)
    if difficulty >= 3 and keyword_ratio >= 0.3 and answer_len >= min_len * 0.5:
        coherence_score += 0.5
    coherence_score = min(2.0, coherence_score)
    score += coherence_score
    reasons.append(f"Coherence: ({coherence_score}/2)")

    return round(min(10.0, score), 1), " | ".join(reasons)

# ============================================================
# PROGRESS TRACKING
# ============================================================

def load_progress():
    """Load curriculum progress from disk."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {
        "started": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "modules": {},
        "total_questions_asked": 0,
        "total_score_sum": 0.0,
        "sessions": 0
    }


def save_progress(progress):
    """Save curriculum progress to disk."""
    progress["last_updated"] = datetime.now().isoformat()
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def get_lesson_progress(progress, module_id, lesson_id):
    """Get or create progress entry for a specific lesson."""
    if module_id not in progress["modules"]:
        progress["modules"][module_id] = {}
    if lesson_id not in progress["modules"][module_id]:
        progress["modules"][module_id][lesson_id] = {
            "scores": [],
            "attempts": 0,
            "mastered": False,
            "avg_score": 0.0,
            "best_score": 0.0,
            "last_attempt": None,
            "answers": []
        }
    return progress["modules"][module_id][lesson_id]

# ============================================================
# KNOWLEDGE BASE STORAGE
# ============================================================

def store_in_knowledge_base(question, answer, score, module_name, lesson_name):
    """Store a good answer in the ASI knowledge base."""
    import hashlib
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

    entry_id = hashlib.md5(f"curriculum:{question[:50]}:{time.time()}".encode()).hexdigest()[:12]
    entry = {
        "id": entry_id,
        "query": question,
        "response": answer[:5000],
        "score": score,
        "source": f"curriculum/{module_name}/{lesson_name}",
        "timestamp": datetime.now().isoformat(),
        "metadata": {"type": "curriculum", "module": module_name, "lesson": lesson_name}
    }

    entry_file = os.path.join(KNOWLEDGE_DIR, f"{entry_id}.json")
    with open(entry_file, "w") as f:
        json.dump(entry, f, indent=2)

    # Update index
    index_file = os.path.join(KNOWLEDGE_DIR, "index.json")
    if os.path.exists(index_file):
        with open(index_file) as f:
            index = json.load(f)
    else:
        index = {"entries": [], "total_queries": 0, "avg_score": 0}

    index["entries"].append({
        "id": entry_id,
        "query": question[:200],
        "score": score,
        "timestamp": entry["timestamp"]
    })
    index["total_queries"] += 1
    scores = [e["score"] for e in index["entries"]]
    index["avg_score"] = round(sum(scores) / len(scores), 2) if scores else 0

    with open(index_file, "w") as f:
        json.dump(index, f, indent=2)

    return entry_id

# ============================================================
# TEACHING ENGINE
# ============================================================

def teach_lesson(module_id, lesson_id, progress, verbose=True):
    """
    Teach a single lesson to the model.
    Ask each question, score the answer, store results.
    """
    module = CURRICULUM[module_id]
    lesson = module["lessons"][lesson_id]
    lesson_progress = get_lesson_progress(progress, module_id, lesson_id)

    module_name = module["name"]
    lesson_name = lesson["name"]

    if verbose:
        print(f"\n{'='*60}")
        print(f"  MODULE: {module_name}")
        print(f"  LESSON: {lesson_name}")
        print(f"  Questions: {len(lesson['questions'])}")
        print(f"  Previous attempts: {lesson_progress['attempts']}")
        print(f"  Current avg score: {lesson_progress['avg_score']}")
        print(f"{'='*60}")

    system_prompt = (
        f"You are Weatherspoon ASI, a distilled artificial superintelligence. "
        f"You are being taught about: {module_name} - {lesson_name}. "
        f"Topics: {', '.join(lesson['topics'])}. "
        f"Answer thoroughly, accurately, and with specific examples. "
        f"Use the Meaningful Examples Convention: every example serves human purpose."
    )

    session_scores = []

    for i, q_data in enumerate(lesson["questions"]):
        question = q_data["q"]
        difficulty = q_data["difficulty"]

        if verbose:
            print(f"\n  Question {i+1}/{len(lesson['questions'])} (difficulty: {difficulty}/4)")
            print(f"  Q: {question[:80]}...")
            print(f"  Thinking...", end="", flush=True)

        start = time.time()
        answer = ollama_generate(question, system=system_prompt)
        elapsed = time.time() - start

        if verbose:
            print(f" ({elapsed:.1f}s)")

        # Score the answer
        score, reasoning = score_answer(answer, q_data)
        session_scores.append(score)

        if verbose:
            print(f"  Score: {score}/10 | {reasoning}")
            if answer and not answer.startswith("[ERROR]"):
                preview = answer[:200].replace("\n", " ")
                print(f"  Answer preview: {preview}...")

        # Store in knowledge base if score is decent
        if score >= 5:
            entry_id = store_in_knowledge_base(
                question, answer, score, module_name, lesson_name
            )
            if verbose:
                print(f"  Stored in knowledge base: {entry_id}")

        # Track in progress
        progress["total_questions_asked"] += 1
        progress["total_score_sum"] += score

    # Update lesson progress
    lesson_progress["scores"].extend(session_scores)
    lesson_progress["attempts"] += 1
    lesson_progress["last_attempt"] = datetime.now().isoformat()
    lesson_progress["avg_score"] = round(
        sum(lesson_progress["scores"]) / len(lesson_progress["scores"]), 1
    ) if lesson_progress["scores"] else 0
    lesson_progress["best_score"] = max(lesson_progress["scores"]) if lesson_progress["scores"] else 0
    lesson_progress["mastered"] = lesson_progress["avg_score"] >= MASTERY_THRESHOLD

    avg = lesson_progress["avg_score"]
    status = "MASTERED" if lesson_progress["mastered"] else "NEEDS WORK"

    if verbose:
        print(f"\n  {'='*40}")
        print(f"  Lesson Complete: {lesson_name}")
        print(f"  Session scores: {session_scores}")
        print(f"  Average: {avg}/10 [{status}]")
        print(f"  {'='*40}")

    save_progress(progress)
    return avg, session_scores

# ============================================================
# CLI COMMANDS
# ============================================================

def cmd_run(progress):
    """Run the next unmastered lesson."""
    for module_id, module in CURRICULUM.items():
        for lesson_id, lesson in module["lessons"].items():
            lp = get_lesson_progress(progress, module_id, lesson_id)
            if not lp["mastered"]:
                print(f"\n  Next unmastered lesson found:")
                print(f"  Module: {module['name']}")
                print(f"  Lesson: {lesson['name']}")
                teach_lesson(module_id, lesson_id, progress)
                return

    print("\n  ALL LESSONS MASTERED!")
    print("  The model has demonstrated competency across all domains.")
    print("  Run 'python3 curriculum.py weak' to find areas for review.")
    print("  Run 'python3 curriculum.py run-all' to re-test everything.\n")


def cmd_run_all(progress):
    """Run all lessons sequentially."""
    total_lessons = sum(len(m["lessons"]) for m in CURRICULUM.values())
    completed = 0

    print(f"\n  RUNNING FULL CURRICULUM ({total_lessons} lessons)")
    print(f"  This will take a while. Ctrl+C to stop and save progress.\n")

    start_time = time.time()

    try:
        for module_id, module in CURRICULUM.items():
            print(f"\n{'#'*60}")
            print(f"  MODULE: {module['name']}")
            print(f"  {module['description']}")
            print(f"{'#'*60}")

            for lesson_id, lesson in module["lessons"].items():
                completed += 1
                print(f"\n  [{completed}/{total_lessons}] {lesson['name']}")
                teach_lesson(module_id, lesson_id, progress)

    except KeyboardInterrupt:
        print(f"\n\n  Interrupted after {completed}/{total_lessons} lessons.")
        print(f"  Progress saved. Resume with 'python3 curriculum.py run'")

    elapsed = time.time() - start_time
    print(f"\n  Total time: {elapsed/60:.1f} minutes")
    print(f"  Lessons completed: {completed}/{total_lessons}")
    cmd_status(progress)


def cmd_status(progress):
    """Show mastery status for every module and lesson."""
    print(f"\n{'='*70}")
    print(f"  CURRICULUM PROGRESS REPORT")
    print(f"  Model: {MODEL}")
    print(f"  Started: {progress.get('started', 'unknown')}")
    print(f"  Last updated: {progress.get('last_updated', 'unknown')}")
    print(f"  Total questions asked: {progress.get('total_questions_asked', 0)}")

    total_q = progress.get("total_questions_asked", 0)
    total_s = progress.get("total_score_sum", 0)
    if total_q > 0:
        print(f"  Overall average score: {total_s/total_q:.1f}/10")
    print(f"{'='*70}")

    total_lessons = 0
    mastered_lessons = 0

    for module_id, module in CURRICULUM.items():
        print(f"\n  MODULE: {module['name']}")
        print(f"  {'-'*50}")

        module_scores = []
        for lesson_id, lesson in module["lessons"].items():
            total_lessons += 1
            lp = get_lesson_progress(progress, module_id, lesson_id)

            avg = lp["avg_score"]
            attempts = lp["attempts"]
            mastered = lp["mastered"]

            if mastered:
                mastered_lessons += 1
                status_icon = "[MASTERED]"
            elif attempts > 0:
                status_icon = "[IN PROGRESS]"
            else:
                status_icon = "[NOT STARTED]"

            module_scores.append(avg)
            score_bar = "#" * int(avg) + "." * (10 - int(avg))
            print(f"    {status_icon:15s} {lesson['name']:45s} {avg:4.1f}/10 [{score_bar}] ({attempts} attempts)")

        if module_scores and any(s > 0 for s in module_scores):
            nonzero = [s for s in module_scores if s > 0]
            module_avg = sum(nonzero) / len(nonzero)
            print(f"    {'Module Average:':62s} {module_avg:.1f}/10")

    print(f"\n{'='*70}")
    print(f"  SUMMARY: {mastered_lessons}/{total_lessons} lessons mastered ({mastered_lessons/total_lessons*100:.0f}%)" if total_lessons else "  No lessons found")
    print(f"  Mastery threshold: {MASTERY_THRESHOLD}/10")
    print(f"{'='*70}\n")


def cmd_weak(progress):
    """Show the weakest lessons that need the most review."""
    weak_lessons = []

    for module_id, module in CURRICULUM.items():
        for lesson_id, lesson in module["lessons"].items():
            lp = get_lesson_progress(progress, module_id, lesson_id)
            if not lp["mastered"]:
                weak_lessons.append({
                    "module": module["name"],
                    "lesson": lesson["name"],
                    "module_id": module_id,
                    "lesson_id": lesson_id,
                    "avg_score": lp["avg_score"],
                    "attempts": lp["attempts"],
                    "gap": MASTERY_THRESHOLD - lp["avg_score"]
                })

    # Sort by score ascending (weakest first)
    weak_lessons.sort(key=lambda x: x["avg_score"])

    print(f"\n{'='*70}")
    print(f"  WEAKEST LESSONS (need review)")
    print(f"{'='*70}")

    if not weak_lessons:
        print(f"\n  All lessons mastered! No weak areas found.")
        print(f"  Consider running 'python3 curriculum.py run-all' for a full re-test.\n")
        return

    for i, wl in enumerate(weak_lessons[:15]):
        status = "NEVER TESTED" if wl["attempts"] == 0 else f"avg {wl['avg_score']}/10"
        print(f"  {i+1:2d}. [{status:15s}] {wl['module']:35s} > {wl['lesson']}")
        if wl["attempts"] > 0:
            print(f"      Gap to mastery: {wl['gap']:.1f} points | Attempts: {wl['attempts']}")

    print(f"\n  Total unmastered: {len(weak_lessons)} lessons")
    print(f"  Run 'python3 curriculum.py run' to teach the next one.")
    print(f"  Run 'python3 curriculum.py teach <module#> <lesson#>' for a specific lesson.\n")


def cmd_teach(progress, module_num, lesson_num):
    """Teach a specific lesson by module and lesson number."""
    module_ids = list(CURRICULUM.keys())

    if module_num < 1 or module_num > len(module_ids):
        print(f"  Module number must be 1-{len(module_ids)}")
        return

    module_id = module_ids[module_num - 1]
    module = CURRICULUM[module_id]
    lesson_ids = list(module["lessons"].keys())

    if lesson_num < 1 or lesson_num > len(lesson_ids):
        print(f"  Lesson number must be 1-{len(lesson_ids)} for module {module_num}")
        return

    lesson_id = lesson_ids[lesson_num - 1]
    teach_lesson(module_id, lesson_id, progress)


def cmd_reset():
    """Reset all progress."""
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print(f"  Progress reset. All lesson data cleared.")
    else:
        print(f"  No progress file found.")

# ============================================================
# MAIN
# ============================================================

def print_banner():
    print("""
+============================================================+
|              AUTO-CURRICULUM SYSTEM                          |
|         Weatherspoon Brother and Sister                     |
|         Alex & David Weatherspoon                              |
|                                                             |
|    "Systematic, progressive, tracked, and never stopping."  |
|                                                             |
|    5 Modules | 34 Lessons | 130+ Questions                  |
|    Teaching weatherspoon-asi to be worthy of the vision      |
+============================================================+
    """)


def print_usage():
    print("""  Commands:
    python3 curriculum.py run           Run the next unmastered lesson
    python3 curriculum.py run-all       Run all lessons (takes hours)
    python3 curriculum.py status        Show mastery per module
    python3 curriculum.py weak          Show weakest lessons needing review
    python3 curriculum.py teach M L     Teach module M, lesson L (e.g. teach 1 3)
    python3 curriculum.py reset         Reset all progress
    """)


def main():
    print_banner()

    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1].lower()

    if command == "reset":
        cmd_reset()
        return

    # Check Ollama for commands that need it
    if command in ("run", "run-all", "teach"):
        if not ollama_available():
            print("  [!] Ollama not running. Start with: ollama serve")
            print("  [!] Model needed: ollama pull weatherspoon-asi")
            sys.exit(1)

    progress = load_progress()
    progress["sessions"] += 1

    if command == "run":
        cmd_run(progress)
    elif command == "run-all":
        cmd_run_all(progress)
    elif command == "status":
        cmd_status(progress)
    elif command == "weak":
        cmd_weak(progress)
    elif command == "teach":
        if len(sys.argv) < 4:
            print("  Usage: python3 curriculum.py teach <module#> <lesson#>")
            print("  Example: python3 curriculum.py teach 1 3  (Module 1, Lesson 3)")
            return
        try:
            m = int(sys.argv[2])
            l = int(sys.argv[3])
            cmd_teach(progress, m, l)
        except ValueError:
            print("  Module and lesson must be numbers. Example: teach 1 3")
    else:
        print(f"  Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    main()
