/**
 * Configuration complète des langues supportées par Esacode
 * Version: 1.0.0
 * Utilisation: import languages from './languages.js'
 */

// Dictionnaire principal des langues avec métadonnées
const LANGUAGES = {
    // Langues principales
    "auto": {
        code: "auto",
        name: "Auto-detect",
        native: "Détection automatique",
        direction: "ltr",
        region: "global",
        family: "auto",
        supported: true
    },
    
    // Langues africaines
    "fon": {
        code: "fon",
        name: "Fon (Bénin)",
        native: "Fɔ̀ngbè",
        direction: "ltr",
        region: "benin",
        family: "gbe",
        supported: true
    },
    "wo": {
        code: "wo",
        name: "Wolof (Sénégal)",
        native: "Wolof",
        direction: "ltr",
        region: "senegal",
        family: "senegambian",
        supported: true
    },
    "aa": {
        code: "aa",
        name: "Afar (Éthiopie)",
        native: "Qafar",
        direction: "ltr",
        region: "ethiopia",
        family: "cushitic",
        supported: true
    },
    "bci": {
        code: "bci",
        name: "Baoulé (Côte d'Ivoire)",
        native: "Baoulé",
        direction: "ltr",
        region: "ivory-coast",
        family: "kwa",
        supported: true
    },
    "bem": {
        code: "bem",
        name: "Bemba (Zambie)",
        native: "Ichibemba",
        direction: "ltr",
        region: "zambia",
        family: "bantu",
        supported: true
    },
    "luo": {
        code: "luo",
        name: "Luo (Tanzanie)",
        native: "Dholuo",
        direction: "ltr",
        region: "tanzania",
        family: "nilotic",
        supported: true
    },
    "bm-Nkoo": {
        code: "bm-Nkoo",
        name: "N'Ko (Mali)",
        native: "N'Ko",
        direction: "rtl",
        region: "mali",
        family: "mande",
        script: "Nko",
        supported: true
    },
    "so": {
        code: "so",
        name: "Somali (Somalie)",
        native: "Soomaali",
        direction: "ltr",
        region: "somalia",
        family: "cushitic",
        supported: true
    },
    // ... (toutes les autres langues africaines)
    "am": {
        code: "am",
        name: "Amharique (Éthiopie)",
        native: "አማርኛ",
        direction: "ltr",
        region: "ethiopia",
        family: "semitic",
        script: "Ethiopic",
        supported: true
    },
    "bm": {
        code: "bm",
        name: "Bambara (Mali)",
        native: "Bamanankan",
        direction: "ltr",
        region: "mali",
        family: "mande",
        supported: true
    },
    "ny": {
        code: "ny",
        name: "Chichewa (Malawi, Zambie, Mozambique)",
        native: "Chichewa",
        direction: "ltr",
        region: "malawi",
        family: "bantu",
        supported: true
    },
    // Continuer pour toutes les langues africaines...
    
    // Langues internationales principales
    "en": {
        code: "en",
        name: "English",
        native: "English",
        direction: "ltr",
        region: "global",
        family: "germanic",
        supported: true
    },
    "fr": {
        code: "fr",
        name: "French (Français)",
        native: "Français",
        direction: "ltr",
        region: "global",
        family: "romance",
        supported: true
    },
    "es": {
        code: "es",
        name: "Spanish (Español)",
        native: "Español",
        direction: "ltr",
        region: "global",
        family: "romance",
        supported: true
    },
    "de": {
        code: "de",
        name: "German (Deutsch)",
        native: "Deutsch",
        direction: "ltr",
        region: "germany",
        family: "germanic",
        supported: true
    },
    "ar": {
        code: "ar",
        name: "Arabic (العربية)",
        native: "العربية",
        direction: "rtl",
        region: "middle-east",
        family: "semitic",
        script: "Arabic",
        supported: true
    },
    "zh": {
        code: "zh",
        name: "Chinese (中文)",
        native: "中文",
        direction: "ltr",
        region: "china",
        family: "sino-tibetan",
        variants: ["zh-CN", "zh-TW"],
        supported: true
    },
    "ja": {
        code: "ja",
        name: "Japanese (日本語)",
        native: "日本語",
        direction: "ltr",
        region: "japan",
        family: "japonic",
        script: "Japanese",
        supported: true
    },
    "ko": {
        code: "ko",
        name: "Korean (한국어)",
        native: "한국어",
        direction: "ltr",
        region: "korea",
        family: "koreanic",
        script: "Hangul",
        supported: true
    },
    "ru": {
        code: "ru",
        name: "Russian (Русский)",
        native: "Русский",
        direction: "ltr",
        region: "russia",
        family: "slavic",
        script: "Cyrillic",
        supported: true
    },
    "pt": {
        code: "pt",
        name: "Portuguese (Português)",
        native: "Português",
        direction: "ltr",
        region: "global",
        family: "romance",
        variants: ["pt-BR", "pt-PT"],
        supported: true
    },
    "it": {
        code: "it",
        name: "Italian (Italiano)",
        native: "Italiano",
        direction: "ltr",
        region: "italy",
        family: "romance",
        supported: true
    },
    "nl": {
        code: "nl",
        name: "Dutch (Nederlands)",
        native: "Nederlands",
        direction: "ltr",
        region: "netherlands",
        family: "germanic",
        supported: true
    },
    "sw": {
        code: "sw",
        name: "Swahili (Kiswahili)",
        native: "Kiswahili",
        direction: "ltr",
        region: "east-africa",
        family: "bantu",
        supported: true
    }
    // Ajouter toutes les autres langues de LANGUAGE_NAMES...
};

// Mapping des codes (normalisation)
const CODE_MAPPING = {
    'auto': 'auto',
    'zh': 'zh-CN',
    'zh-hans': 'zh-CN',
    'zh-hant': 'zh-TW',
    'zh-cn': 'zh-CN',
    'zh-tw': 'zh-TW',
    'zh-hk': 'zh-TW',
    'chi': 'zh-CN',
    'iw': 'he',
    'jw': 'jv',
    'nb': 'no',
    'nn': 'no',
    'baq': 'eu',
    'cze': 'cs',
    'dut': 'nl',
    'ger': 'de',
    'gre': 'el',
    'arm': 'hy',
    'ice': 'is',
    'per': 'fa',
    'rum': 'ro',
    'en-us': 'en',
    'en-gb': 'en',
    'fr-ca': 'fr',
    'fr-fr': 'fr',
    'pt-br': 'pt',
    'pt-pt': 'pt',
    'es-es': 'es',
    'es-mx': 'es',
    'fil': 'tl',
    'he': 'iw',
    'ji': 'yi',
    'in': 'id',
    'gav': 'sw',
    // Ajouter tous les codes de LANGUAGE_CODES...
    ...Object.fromEntries(
        Object.keys(LANGUAGES).map(code => [code, code])
    )
};

// Utilitaires
const LanguageUtils = {
    /**
     * Obtenir une langue par code
     */
    getLanguage: (code) => {
        const normalized = CODE_MAPPING[code.toLowerCase()] || code.toLowerCase();
        return LANGUAGES[normalized] || LANGUAGES['auto'];
    },
    
    /**
     * Obtenir toutes les langues supportées
     */
    getSupportedLanguages: () => {
        return Object.values(LANGUAGES)
            .filter(lang => lang.supported)
            .sort((a, b) => a.name.localeCompare(b.name));
    },
    
    /**
     * Filtrer par région
     */
    getLanguagesByRegion: (region) => {
        return Object.values(LANGUAGES)
            .filter(lang => lang.region === region && lang.supported)
            .sort((a, b) => a.name.localeCompare(b.name));
    },
    
    /**
     * Vérifier si une langue est supportée
     */
    isSupported: (code) => {
        return !!LANGUAGES[CODE_MAPPING[code.toLowerCase()] || code.toLowerCase()];
    },
    
    /**
     * Normaliser un code de langue
     */
    normalizeCode: (code) => {
        return CODE_MAPPING[code.toLowerCase()] || code.toLowerCase();
    },
    
    /**
     * Obtenir les langues africaines
     */
    getAfricanLanguages: () => {
        return Object.values(LANGUAGES)
            .filter(lang => 
                ['benin', 'senegal', 'ethiopia', 'ivory-coast', 'zambia', 
                 'tanzania', 'mali', 'somalia', 'malawi'].includes(lang.region)
            );
    }
};

// Export pour différents modules
if (typeof module !== 'undefined' && module.exports) {
    // CommonJS
    module.exports = { LANGUAGES, CODE_MAPPING, LanguageUtils };
} else if (typeof define === 'function' && define.amd) {
    // AMD
    define([], () => ({ LANGUAGES, CODE_MAPPING, LanguageUtils }));
} else {
    // Global (browser)
    window.EsaCodeLanguages = { LANGUAGES, CODE_MAPPING, LanguageUtils };
}

// Export ES6
export { LANGUAGES, CODE_MAPPING, LanguageUtils };