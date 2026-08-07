import type { LanguageCode } from "./sevens-greetings";

export type ConvoStrings = {
  userQuestion: string;
  verifiedAnswer: string;
  confidence: string;
  title: string;
  intro: (a: string, b: string, c: string) => string;
  paraClose: string;
  colDb: string;
  colLatency: string;
  colCost: string;
  colOps: string;
  ops: [string, string, string];
  sourcesLabel: string;
  sources: { title: string; domain: string; relevance: number }[];
  copy: string;
  share: string;
  disclaimer: string;
  sessionTitle: string;
  placeholder: string;
  enterToSend: string;
  intelligence: string;
  live: string;
  workspace: string;
  newSession: string;
};

const en: ConvoStrings = {
  userQuestion:
    "Compare the leading vector databases for a mid-size RAG deployment. Focus on latency, cost, and operational overhead.",
  verifiedAnswer: "Verified answer",
  confidence: "98% confidence",
  title: "Three databases fit most mid-size RAG stacks",
  intro: (a, b, c) =>
    `For a mid-size retrieval-augmented deployment, the practical short list is ${a}, ${b}, and ${c}. Each trades differently across latency, cost, and how much infrastructure your team owns. The right pick depends less on raw benchmarks and more on where you want the operational burden to sit.`,
  paraClose:
    "If speed of iteration matters most, start with Pinecone. If cost efficiency and portability rank higher, Qdrant is the strongest pick today. Weaviate excels when hybrid search and rich schemas are core to the product.",
  colDb: "Database",
  colLatency: "Latency (p95)",
  colCost: "Cost / 1M vectors",
  colOps: "Ops overhead",
  ops: [
    "Minimal — fully managed",
    "Low — cloud or self-host",
    "Medium — modules to tune",
  ],
  sourcesLabel: "Sources",
  sources: [
    { title: "Vector DB benchmarks 2025", domain: "arxiv.org", relevance: 96 },
    { title: "Scaling RAG at production", domain: "pinecone.io", relevance: 91 },
    { title: "Qdrant vs Weaviate deep dive", domain: "qdrant.tech", relevance: 88 },
  ],
  copy: "Copy",
  share: "Share",
  disclaimer: "sevens verifies key claims. Review sources for critical decisions.",
  sessionTitle: "Q3 competitive landscape",
  placeholder: "Ask anything…",
  enterToSend: "⏎ to send",
  intelligence: "Intelligence",
  live: "Live",
  workspace: "Workspace",
  newSession: "New session",
};

const te: ConvoStrings = {
  userQuestion:
    "మధ్యస్థ RAG విస్తరణ కోసం ప్రముఖ వెక్టర్ డేటాబేస్‌లను పోల్చండి. లేటెన్సీ, ఖర్చు, మరియు నిర్వహణ భారంపై దృష్టి పెట్టండి.",
  verifiedAnswer: "ధృవీకరించిన సమాధానం",
  confidence: "98% విశ్వాసం",
  title: "మధ్యస్థ RAG స్టాక్‌లకు మూడు డేటాబేస్‌లు అనుకూలం",
  intro: (a, b, c) =>
    `మధ్యస్థ retrieval-augmented విస్తరణ కోసం ఆచరణాత్మక ఎంపికలు ${a}, ${b}, మరియు ${c}. ప్రతి ఒక్కటి లేటెన్సీ, ఖర్చు, మరియు మీ బృందం స్వంతం చేసుకునే మౌలిక సదుపాయాల విషయంలో వేర్వేరుగా ఉంటాయి. సరైన ఎంపిక ముడి బెంచ్‌మార్క్‌ల కంటే నిర్వహణ భారం ఎక్కడ ఉండాలో దానిపై ఆధారపడి ఉంటుంది.`,
  paraClose:
    "వేగవంతమైన ఇటరేషన్ ముఖ్యమైతే Pinecone తో ప్రారంభించండి. ఖర్చు సామర్థ్యం, పోర్టబిలిటీ ముఖ్యమైతే Qdrant నేటికి ఉత్తమ ఎంపిక. హైబ్రిడ్ శోధన, రిచ్ స్కీమాలు అవసరమైతే Weaviate ఉత్తమం.",
  colDb: "డేటాబేస్",
  colLatency: "లేటెన్సీ (p95)",
  colCost: "ఖర్చు / 1M వెక్టర్లు",
  colOps: "నిర్వహణ భారం",
  ops: [
    "తక్కువ — పూర్తిగా నిర్వహించబడుతుంది",
    "తక్కువ — క్లౌడ్ లేదా స్వీయ హోస్ట్",
    "మధ్యస్థం — మాడ్యూల్స్ ట్యూన్ చేయాలి",
  ],
  sourcesLabel: "మూలాలు",
  sources: [
    { title: "వెక్టర్ DB బెంచ్‌మార్క్‌లు 2025", domain: "arxiv.org", relevance: 96 },
    { title: "ఉత్పత్తిలో RAG స్కేలింగ్", domain: "pinecone.io", relevance: 91 },
    { title: "Qdrant vs Weaviate లోతైన విశ్లేషణ", domain: "qdrant.tech", relevance: 88 },
  ],
  copy: "కాపీ",
  share: "పంచుకోండి",
  disclaimer:
    "sevens ముఖ్య వాదనలను ధృవీకరిస్తుంది. కీలక నిర్ణయాలకు మూలాలను సమీక్షించండి.",
  sessionTitle: "Q3 పోటీ దృశ్యం",
  placeholder: "ఏదైనా అడగండి…",
  enterToSend: "⏎ పంపడానికి",
  intelligence: "మేధస్సు",
  live: "ప్రత్యక్షం",
  workspace: "వర్క్‌స్పేస్",
  newSession: "కొత్త సెషన్",
};

const hi: ConvoStrings = {
  ...en,
  userQuestion:
    "मध्यम आकार के RAG परिनियोजन के लिए प्रमुख वेक्टर डेटाबेस की तुलना करें। लेटेंसी, लागत और परिचालन भार पर ध्यान दें।",
  verifiedAnswer: "सत्यापित उत्तर",
  confidence: "98% विश्वास",
  title: "अधिकांश मध्यम RAG स्टैक के लिए तीन डेटाबेस उपयुक्त हैं",
  paraClose:
    "यदि तेज़ पुनरावृत्ति सबसे महत्वपूर्ण है, तो Pinecone से शुरू करें। यदि लागत दक्षता और पोर्टेबिलिटी अधिक हैं, तो Qdrant आज सबसे मज़बूत विकल्प है। Weaviate वहाँ उत्कृष्ट है जहाँ हाइब्रिड खोज और समृद्ध स्कीमा उत्पाद का आधार हैं।",
  disclaimer: "sevens मुख्य दावों की पुष्टि करता है। महत्वपूर्ण निर्णयों के लिए स्रोत देखें।",
  placeholder: "कुछ भी पूछें…",
  intelligence: "इंटेलिजेंस",
  workspace: "वर्कस्पेस",
  newSession: "नया सत्र",
};

const TABLE: Partial<Record<LanguageCode, ConvoStrings>> = { en, te, hi };

export function convo(lang: LanguageCode): ConvoStrings {
  return TABLE[lang] ?? en;
}

export function personalize(greeting: string, name: string): string {
  if (!name) return greeting;
  // Insert name after first sentence-opening clause: replace first ". " or "? " with ", Name.  "
  const idx = greeting.search(/[.?!]\s/);
  if (idx > 0) {
    return `${greeting.slice(0, idx)}, ${name}${greeting.slice(idx)}`;
  }
  return `${greeting}, ${name}`;
}