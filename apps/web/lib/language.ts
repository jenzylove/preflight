/**
 * Plain English for things the system stores in codes.
 *
 * Preflight measures files and compares them against published specifications,
 * so internally it speaks in ISO codes, field paths and comparison operators.
 * None of that belongs on the screen where a filmmaker is deciding what to do
 * next. A first-time user should never have to know what `GB`, `eq`, or
 * `audio.integratedLoudnessLufs` mean in order to know which button to press.
 *
 * The precise value is never thrown away. Every screen that translates keeps
 * the exact figure available one layer deeper, under technical details.
 */

/** Countries, most-used first, then alphabetical. ISO 3166-1 alpha-2. */
export const COUNTRIES: { code: string; name: string }[] = [
  { code: "NG", name: "Nigeria" },
  { code: "GB", name: "United Kingdom" },
  { code: "US", name: "United States" },
  { code: "AR", name: "Argentina" },
  { code: "AU", name: "Australia" },
  { code: "AT", name: "Austria" },
  { code: "BE", name: "Belgium" },
  { code: "BR", name: "Brazil" },
  { code: "CA", name: "Canada" },
  { code: "CL", name: "Chile" },
  { code: "CN", name: "China" },
  { code: "CO", name: "Colombia" },
  { code: "HR", name: "Croatia" },
  { code: "CZ", name: "Czechia" },
  { code: "DK", name: "Denmark" },
  { code: "EG", name: "Egypt" },
  { code: "EE", name: "Estonia" },
  { code: "FI", name: "Finland" },
  { code: "FR", name: "France" },
  { code: "DE", name: "Germany" },
  { code: "GH", name: "Ghana" },
  { code: "GR", name: "Greece" },
  { code: "HU", name: "Hungary" },
  { code: "IS", name: "Iceland" },
  { code: "IN", name: "India" },
  { code: "ID", name: "Indonesia" },
  { code: "IE", name: "Ireland" },
  { code: "IL", name: "Israel" },
  { code: "IT", name: "Italy" },
  { code: "JP", name: "Japan" },
  { code: "KE", name: "Kenya" },
  { code: "LV", name: "Latvia" },
  { code: "LT", name: "Lithuania" },
  { code: "MX", name: "Mexico" },
  { code: "MA", name: "Morocco" },
  { code: "NL", name: "Netherlands" },
  { code: "NZ", name: "New Zealand" },
  { code: "NO", name: "Norway" },
  { code: "PK", name: "Pakistan" },
  { code: "PE", name: "Peru" },
  { code: "PH", name: "Philippines" },
  { code: "PL", name: "Poland" },
  { code: "PT", name: "Portugal" },
  { code: "RO", name: "Romania" },
  { code: "RU", name: "Russia" },
  { code: "SA", name: "Saudi Arabia" },
  { code: "SN", name: "Senegal" },
  { code: "RS", name: "Serbia" },
  { code: "SG", name: "Singapore" },
  { code: "ZA", name: "South Africa" },
  { code: "KR", name: "South Korea" },
  { code: "ES", name: "Spain" },
  { code: "SE", name: "Sweden" },
  { code: "CH", name: "Switzerland" },
  { code: "TW", name: "Taiwan" },
  { code: "TZ", name: "Tanzania" },
  { code: "TH", name: "Thailand" },
  { code: "TR", name: "Türkiye" },
  { code: "UG", name: "Uganda" },
  { code: "UA", name: "Ukraine" },
  { code: "AE", name: "United Arab Emirates" },
  { code: "UY", name: "Uruguay" },
  { code: "VN", name: "Vietnam" },
];

/** Languages by name. The stored value stays the ISO 639-1 code. */
export const LANGUAGES: { code: string; name: string }[] = [
  { code: "en", name: "English" },
  { code: "fr", name: "French" },
  { code: "es", name: "Spanish" },
  { code: "pt", name: "Portuguese" },
  { code: "ar", name: "Arabic" },
  { code: "zh", name: "Chinese" },
  { code: "hi", name: "Hindi" },
  { code: "sw", name: "Swahili" },
  { code: "yo", name: "Yoruba" },
  { code: "ig", name: "Igbo" },
  { code: "ha", name: "Hausa" },
  { code: "de", name: "German" },
  { code: "it", name: "Italian" },
  { code: "ru", name: "Russian" },
  { code: "ja", name: "Japanese" },
  { code: "ko", name: "Korean" },
  { code: "nl", name: "Dutch" },
  { code: "pl", name: "Polish" },
  { code: "tr", name: "Turkish" },
  { code: "uk", name: "Ukrainian" },
  { code: "sv", name: "Swedish" },
  { code: "no", name: "Norwegian" },
  { code: "da", name: "Danish" },
  { code: "fi", name: "Finnish" },
  { code: "he", name: "Hebrew" },
  { code: "fa", name: "Persian" },
  { code: "th", name: "Thai" },
  { code: "vi", name: "Vietnamese" },
  { code: "id", name: "Indonesian" },
];

export function countryName(code: string | null | undefined): string | null {
  if (!code) return null;
  return COUNTRIES.find((c) => c.code === code)?.name ?? code;
}

export function languageName(code: string | null | undefined): string | null {
  if (!code) return null;
  return LANGUAGES.find((l) => l.code === code)?.name ?? code;
}

/**
 * What kind of work this is.
 *
 * The backend taxonomy is a closed set, and "documentary" and "feature" sit in
 * it side by side even though a film can obviously be both. Rather than
 * pretend otherwise, each option says what it is *for* - the length and shape
 * the destination will expect - so someone picking one is choosing a delivery
 * shape rather than declaring a genre.
 */
export const PROJECT_TYPES: {
  value: string;
  label: string;
  hint: string;
}[] = [
  {
    value: "feature",
    label: "Feature film",
    hint: "A full-length film, usually over 40 minutes. Choose this for a feature-length documentary too.",
  },
  {
    value: "short",
    label: "Short film",
    hint: "Under about 40 minutes.",
  },
  {
    value: "documentary",
    label: "Documentary (short)",
    hint: "A short-form documentary. For a feature-length one, choose Feature film.",
  },
  {
    value: "series",
    label: "Series episode",
    hint: "One episode of an ongoing series.",
  },
  {
    value: "trailer",
    label: "Trailer or promo",
    hint: "A trailer, teaser or promotional cut.",
  },
  {
    value: "other",
    label: "Something else",
    hint: "Anything that does not fit the shapes above.",
  },
];

/**
 * Field paths, in the words a filmmaker would use.
 *
 * The key is `assetType.fieldName` exactly as the rule contract names it. A
 * field with no entry falls back to a readable version of its own name rather
 * than disappearing, so a newly researched destination naming a field nobody
 * has translated yet still reads as English rather than as camelCase.
 */
const FIELD_LABELS: Record<string, string> = {
  "video.container": "Video file type",
  "video.codec": "Video format",
  "video.profile": "Video encoding profile",
  "video.widthPx": "Picture width",
  "video.heightPx": "Picture height",
  "video.frameRate": "Frame rate",
  "video.displayAspectRatio": "Aspect ratio",
  "video.bitrateBps": "Video quality (bitrate)",
  "video.colourPrimaries": "Colour standard",
  "video.colourTransfer": "Colour transfer",
  "video.colourMatrix": "Colour matrix",
  "video.scanType": "Scan type",
  "video.fastStart": "Web-optimised layout",
  "video.durationSeconds": "Length",

  "audio.codec": "Audio format",
  "audio.channels": "Audio channels",
  "audio.sampleRateHz": "Audio sample rate",
  "audio.bitrateBps": "Audio quality (bitrate)",
  "audio.integratedLoudnessLufs": "Audio loudness",
  "audio.truePeakDbtp": "Audio peak level",
  "audio.loudnessRangeLu": "Audio dynamic range",

  "subtitle.format": "Subtitle file type",
  "subtitle.language": "Subtitle language",
  "subtitle.burnedIn": "Subtitles burned into the picture",

  "poster.format": "Poster file type",
  "poster.widthPx": "Poster width",
  "poster.heightPx": "Poster height",

  "metadata.title": "Title",
  "metadata.language": "Language",
  "metadata.runtimeSeconds": "Runtime",
  "metadata.countryOfOrigin": "Country of origin",
  "metadata.synopsisChars": "Summary length",

  "package.fileNamePattern": "File naming",
  "package.fileCount": "Number of files",
  "package.totalBytes": "Total size",
};

export function fieldLabel(assetType: string, fieldName: string): string {
  const key = `${assetType}.${fieldName}`;
  const known = FIELD_LABELS[key];
  if (known) return known;
  // camelCase to words, so an untranslated field still reads as English.
  const words = fieldName
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/Px$/, "")
    .replace(/Bps$/, "")
    .toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * A published requirement, as a sentence.
 *
 * "Published: eq jpeg2000" is a comparison. "Berlinale asks for JPEG 2000" is
 * a fact someone can act on. The operator carries the meaning, so it is spelled
 * out rather than shown as a symbol.
 */
export function requirementSentence(
  destination: string,
  assetType: string,
  fieldName: string,
  operator: string,
  expected: unknown,
): string {
  const what = fieldLabel(assetType, fieldName).toLowerCase();
  const value = formatValue(expected, fieldName);
  const who = destination;

  switch (operator) {
    case "eq":
      return `${who} asks for ${what} to be ${value}.`;
    case "neq":
      return `${who} does not accept ${what} of ${value}.`;
    case "gte":
      return `${who} asks for ${what} of at least ${value}.`;
    case "lte":
      return `${who} asks for ${what} of no more than ${value}.`;
    case "between":
      return `${who} asks for ${what} between ${value}.`;
    case "any_of_ranges":
      return `${who} accepts ${what} in any of these ranges: ${value}.`;
    case "in":
      return `${who} accepts ${what} of ${value}.`;
    case "not_in":
      return `${who} does not accept ${what} of ${value}.`;
    case "present":
      return `${who} requires ${what} to be provided.`;
    case "absent":
      return `${who} requires ${what} to be absent.`;
    default:
      return `${who} requires ${what}: ${value}.`;
  }
}

/**
 * Values in a form a person reads, without losing what they are.
 *
 * The API sends published values as strings, so a range arrives as the literal
 * "[82000000.0, 102000000.0]". Printed as-is that is worse than no help at
 * all, so ranges are parsed back into numbers and given units. A codec
 * identifier gets the name people use for it. Everything keeps its exact
 * value under technical details.
 */
export function formatValue(value: unknown, field?: string): string {
  if (value === null || value === undefined || value === "") return "not measured";
  if (typeof value === "boolean") return value ? "yes" : "no";

  if (Array.isArray(value)) {
    if (value.length === 2 && value.every((v) => typeof v === "number")) {
      return `${formatValue(value[0], field)} and ${formatValue(value[1], field)}`;
    }
    return value.map((v) => formatValue(v, field)).join(", ");
  }

  if (typeof value === "string") {
    // A stringified list or range, which is how the API sends them.
    const trimmed = value.trim();
    if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
      try {
        const parsed = JSON.parse(trimmed.replace(/'/g, '"'));
        if (Array.isArray(parsed)) return formatValue(parsed, field);
      } catch {
        // Not JSON after all. Fall through and print it plainly.
      }
    }
    const named = codecName(trimmed);
    return named ?? trimmed;
  }

  if (typeof value === "number") {
    if (field === "bitrateBps") {
      if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)} Mbps`;
      return `${Math.round(value / 1000)} kbps`;
    }
    if (field === "integratedLoudnessLufs") return `${value} LUFS`;
    if (field === "truePeakDbtp") return `${value} dBTP`;
    if (field === "loudnessRangeLu") return `${value} LU`;
    if (field === "sampleRateHz") return `${(value / 1000).toFixed(0)} kHz`;
    if (field === "channels") return value === 1 ? "mono" : value === 2 ? "stereo" : `${value} channels`;
    if (field === "durationSeconds") return formatDuration(value) ?? String(value);
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)} million`;
    return String(value);
  }
  return String(value);
}

/** Seconds as a length someone would say out loud. */
export function formatDuration(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined) return null;
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  if (minutes === 0) return `${rest}s`;
  return `${minutes}m ${String(rest).padStart(2, "0")}s`;
}

/** 1920x1080 is "1080p" to almost everyone who is not a broadcast engineer. */
export function resolutionName(
  width: number | null | undefined,
  height: number | null | undefined,
): string | null {
  if (!width || !height) return null;
  const known: Record<number, string> = {
    2160: "4K (2160p)",
    1440: "1440p",
    1080: "1080p",
    720: "720p",
    576: "576p",
    480: "480p",
  };
  return known[height] ?? `${width}×${height}`;
}

/** Codec identifiers as the names people actually use for them. */
export function codecName(codec: string | null | undefined): string | null {
  if (!codec) return null;
  const known: Record<string, string> = {
    h264: "H.264",
    avc: "H.264",
    hevc: "H.265",
    h265: "H.265",
    prores: "ProRes",
    proreslt: "ProRes LT",
    "prores lt": "ProRes LT",
    jpeg2000: "JPEG 2000",
    aac: "AAC",
    ac3: "AC-3",
    "ac-3": "AC-3",
    lpcm: "PCM",
    pcm: "PCM",
    mp3: "MP3",
  };
  return known[codec.toLowerCase()] ?? codec;
}

/**
 * Repair operations, in the words of the person whose film it is.
 *
 * `normalise_loudness` and `rewrite_container_metadata` were on screen in
 * production. They are precise and they are ours, not the user's. The
 * identifier stays available under technical details, because it is what the
 * passport and the worker log record.
 */
const OPERATION_LABELS: Record<string, string> = {
  normalise_loudness: "Adjust audio loudness",
  rewrite_container_metadata: "Update delivery metadata",
  convert_subtitles: "Converting the subtitle file",
  resize_poster: "Resizing the poster",
  normalise_metadata: "Reformatting the delivery details",
  rename_and_layout: "Naming the files as the destination asks",
  build_manifest: "Recording a checksum for every file",
  reencode_video: "Re-encoding the picture",
  crop_poster: "Cropping the poster",
  translate_subtitles: "Translating the subtitles",
  technical_conform: "Preparing the technical conform",
};

/** Past tense, for describing what was already done. */
const OPERATION_DONE: Record<string, string> = {
  normalise_loudness: "Adjusted the audio loudness",
  rewrite_container_metadata: "Updated the delivery metadata",
  convert_subtitles: "Converted the subtitle file",
  resize_poster: "Resized the poster",
  normalise_metadata: "Reformatted the delivery details",
  rename_and_layout: "Named the files as the destination asks",
  build_manifest: "Recorded a checksum for every file",
};

export function operationLabel(operation: string): string {
  return OPERATION_LABELS[operation] ?? humaniseIdentifier(operation);
}

export function operationDone(operation: string): string {
  return OPERATION_DONE[operation] ?? humaniseIdentifier(operation);
}

/** An operation nobody has named yet still reads as English, not as code. */
function humaniseIdentifier(value: string): string {
  const words = value.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * What a person can actually do about a requirement Preflight will not fix.
 *
 * Reporting "needs your decision" and stopping is not a decision point, it is
 * a dead end. Every one of these has a real answer, and the answer is almost
 * always work done outside Preflight and brought back - so it says which work,
 * and says that coming back means uploading the new version and checking
 * again.
 */
export function whatYouCanDo(assetType: string, fieldName: string): string {
  const key = `${assetType}.${fieldName}`;
  const advice: Record<string, string> = {
    "audio.channels":
      "Ask whoever mixed the film for a version with this channel layout. A "
      + "re-mix is the only way to get there honestly; folding or spreading "
      + "channels automatically would change how the film sounds.",
    "audio.codec":
      "Export a version with this audio format from your editing or mastering "
      + "software, where you can hear the result before committing to it.",
    "audio.sampleRateHz":
      "Export a version at this sample rate from your editing software.",
    "audio.bitrateBps":
      "Export the audio at this data rate from your editing or mastering "
      + "software.",
    "video.codec":
      "Export a new master in this format from your editing software, where "
      + "you can check the result frame by frame.",
    "video.bitrateBps":
      "Export a new master at this data rate. Your editing or encoding "
      + "software will let you judge the quality before you deliver it.",
    "video.widthPx":
      "Export a new master at this size rather than scaling the existing one.",
    "video.heightPx":
      "Export a new master at this size rather than scaling the existing one.",
    "video.frameRate":
      "Export a new master at this frame rate. Converting between rates "
      + "changes motion, so it is worth watching the result.",
    "video.profile":
      "Export a new master with this encoding profile from your editing "
      + "software.",
    "video.container":
      "Export a new master as this file type from your editing software.",
    "subtitle.burnedIn":
      "This destination wants the subtitles visible in the picture itself. "
      + "Burn them in when you export, then upload that version.",
    "subtitle.language":
      "Supply a subtitle file in this language. A translation needs a person "
      + "who speaks it, so Preflight will not generate one.",
  };

  return (
    advice[key]
    ?? "This one needs a change Preflight will not make on your behalf. Make it "
       + "wherever you finish your film, then upload the new version."
  );
}

export interface RequirementAction {
  label: string;
  href: string;
  instruction: string;
}

/** Give every unresolved requirement a concrete next click. */
export function requirementAction(
  assetType: string,
  fieldName: string,
  projectId: string,
): RequirementAction {
  if (assetType === "subtitle" && fieldName === "burnedIn") {
    return {
      label: "Replace film",
      href: `/projects/${projectId}/master#master-upload`,
      instruction: "Export the film with the required subtitle treatment, then replace the film in Preflight.",
    };
  }
  if (assetType === "subtitle") {
    return {
      label: "Add subtitle file",
      href: `/projects/${projectId}/master#subtitle-upload`,
      instruction: "Add the subtitle file, then run the check again.",
    };
  }
  if (assetType === "poster") {
    return {
      label: "Add poster",
      href: `/projects/${projectId}/master#poster-upload`,
      instruction: "Add the poster file, then run the check again.",
    };
  }
  if (assetType === "metadata" || assetType === "package") {
    return {
      label: "Edit delivery details",
      href: `/projects/${projectId}/destinations`,
      instruction: "Update the delivery details, then run the check again.",
    };
  }
  return {
    label: "Replace film",
    href: `/projects/${projectId}/master#master-upload`,
    instruction: "Replace the film with the corrected version, then run the check again.",
  };
}

/** The one sentence that closes the loop after work done elsewhere. */
export const COME_BACK =
  "When you have the new version, upload it here and run the check again.";
