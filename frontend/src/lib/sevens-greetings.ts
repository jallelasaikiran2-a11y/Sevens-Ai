// Dynamic multilingual greeting library for sevens.
// Greetings are keyed by language and time-of-day bucket. A per-browser
// recency log prevents repeating the same greeting for ~7 days.

export type TimeBucket = "morning" | "afternoon" | "evening" | "night";

export const LANGUAGES = [
  { code: "en", label: "English", native: "English" },
  { code: "hi", label: "Hindi", native: "हिन्दी" },
  { code: "te", label: "Telugu", native: "తెలుగు" },
  { code: "ta", label: "Tamil", native: "தமிழ்" },
  { code: "kn", label: "Kannada", native: "ಕನ್ನಡ" },
  { code: "ml", label: "Malayalam", native: "മലയാളം" },
  { code: "mr", label: "Marathi", native: "मराठी" },
  { code: "gu", label: "Gujarati", native: "ગુજરાતી" },
  { code: "pa", label: "Punjabi", native: "ਪੰਜਾਬੀ" },
  { code: "bn", label: "Bengali", native: "বাংলা" },
  { code: "or", label: "Odia", native: "ଓଡ଼ିଆ" },
  { code: "as", label: "Assamese", native: "অসমীয়া" },
  { code: "ur", label: "Urdu", native: "اردو" },
  { code: "sa", label: "Sanskrit", native: "संस्कृतम्" },
  { code: "ne", label: "Nepali", native: "नेपाली" },
  { code: "mai", label: "Maithili", native: "मैथिली" },
  { code: "kok", label: "Konkani", native: "कोंकणी" },
  { code: "sd", label: "Sindhi", native: "سنڌي" },
  { code: "ks", label: "Kashmiri", native: "کٲشُر" },
  { code: "doi", label: "Dogri", native: "डोगरी" },
  { code: "mni", label: "Manipuri", native: "মৈতৈলোন্" },
  { code: "sat", label: "Santali", native: "ᱥᱟᱱᱛᱟᱲᱤ" },
  { code: "brx", label: "Bodo", native: "बड़ो" },
] as const;

export type LanguageCode = (typeof LANGUAGES)[number]["code"];

export function getTimeBucket(d = new Date()): TimeBucket {
  const h = d.getHours();
  if (h >= 5 && h < 12) return "morning";
  if (h >= 12 && h < 17) return "afternoon";
  if (h >= 17 && h < 22) return "evening";
  return "night";
}

type GreetingSet = Record<TimeBucket, string[]>;

// Curated, natively-phrased greetings. Each bucket carries several
// options so rotation feels organic rather than templated.
export const GREETINGS: Record<LanguageCode, GreetingSet> = {
  en: {
    morning: [
      "Good morning. What are we exploring today?",
      "A fresh start. What would you like to work on?",
      "Morning. Where should we begin?",
      "Ready when you are. What's first?",
    ],
    afternoon: [
      "Welcome back. What's today's focus?",
      "Good afternoon. What can I help you think through?",
      "Picking up where we left off — what's next?",
      "What would you like to explore this afternoon?",
    ],
    evening: [
      "Hope your day is going well. What can I help you solve?",
      "Good evening. What are we untangling tonight?",
      "Evening. What's on your mind?",
      "Let's make the last few hours count.",
    ],
    night: [
      "Working late? Let's make it productive.",
      "Quiet hours. Perfect for deep thinking.",
      "Still here. What would you like to work through?",
      "The best ideas often arrive late. What's yours?",
    ],
  },
  hi: {
    morning: [
      "सुप्रभात। आज हम किस पर काम करें?",
      "नमस्कार। दिन की शुरुआत कहाँ से करें?",
      "स्वागत है। आज क्या सोच रहे हैं?",
    ],
    afternoon: [
      "नमस्कार। आज का मुख्य कार्य क्या है?",
      "स्वागत है। किस विषय पर आगे बढ़ें?",
      "बताइए, आज किसमें मदद करूँ?",
    ],
    evening: [
      "शुभ संध्या। आज कैसा दिन रहा?",
      "नमस्कार। इस समय क्या करना चाहेंगे?",
      "बताइए, किस पर विचार करना है?",
    ],
    night: [
      "देर रात तक काम? चलिए इसे सार्थक बनाते हैं।",
      "शांत समय — गहरे विचार के लिए बेहतरीन।",
      "बताइए, क्या मन में है?",
    ],
  },
  te: {
    morning: [
      "శుభోదయం. ఈరోజు ఏమి ప్రారంభిద్దాం?",
      "నమస్కారం. ఈరోజు దేని మీద పని చేద్దాం?",
      "స్వాగతం. మొదట ఏమి చేద్దాం?",
    ],
    afternoon: [
      "నమస్కారం. ఈరోజు ప్రధాన లక్ష్యం ఏమిటి?",
      "మధ్యాహ్న శుభాకాంక్షలు. ఏమి ఆలోచిస్తున్నారు?",
      "చెప్పండి, ఎందులో సహాయం కావాలి?",
    ],
    evening: [
      "శుభ సాయంత్రం. ఈరోజు ఎలా గడిచింది?",
      "నమస్కారం. ఇప్పుడు ఏమి చేద్దాం?",
      "చెప్పండి, దేని గురించి ఆలోచిద్దాం?",
    ],
    night: [
      "ఇంకా పని చేస్తున్నారా? ఉపయోగకరంగా చేద్దాం.",
      "నిశ్శబ్ద సమయం — లోతైన ఆలోచనలకు అనుకూలం.",
      "చెప్పండి, మీ మనసులో ఏముంది?",
    ],
  },
  ta: {
    morning: [
      "காலை வணக்கம். இன்று எதில் தொடங்கலாம்?",
      "வணக்கம். இன்று என்ன செய்யலாம்?",
      "வரவேற்கிறேன். எங்கிருந்து ஆரம்பிக்கலாம்?",
    ],
    afternoon: [
      "வணக்கம். இன்றைய முக்கிய பணி என்ன?",
      "மதிய வணக்கம். எதில் உதவலாம்?",
      "சொல்லுங்கள், என்ன யோசிக்கிறீர்கள்?",
    ],
    evening: [
      "மாலை வணக்கம். நாள் எப்படி இருந்தது?",
      "வணக்கம். இப்போது என்ன செய்யலாம்?",
      "சொல்லுங்கள், எதைப் பற்றி பேசலாம்?",
    ],
    night: [
      "இரவிலும் வேலையா? பயனுள்ளதாக ஆக்கலாம்.",
      "அமைதியான நேரம் — ஆழ்ந்த சிந்தனைக்கு ஏற்றது.",
      "சொல்லுங்கள், மனதில் என்ன இருக்கிறது?",
    ],
  },
  kn: {
    morning: [
      "ಶುಭೋದಯ. ಇಂದು ಏನನ್ನು ಆರಂಭಿಸೋಣ?",
      "ನಮಸ್ಕಾರ. ಇಂದು ಯಾವುದರ ಮೇಲೆ ಕೆಲಸ ಮಾಡೋಣ?",
    ],
    afternoon: [
      "ನಮಸ್ಕಾರ. ಇಂದಿನ ಗುರಿ ಏನು?",
      "ಶುಭ ಮಧ್ಯಾಹ್ನ. ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?",
    ],
    evening: [
      "ಶುಭ ಸಂಜೆ. ದಿನ ಹೇಗಿತ್ತು?",
      "ನಮಸ್ಕಾರ. ಈಗ ಏನು ಮಾಡೋಣ?",
    ],
    night: [
      "ರಾತ್ರಿಯೂ ಕೆಲಸ? ಇದನ್ನು ಫಲಪ್ರದವಾಗಿಸೋಣ.",
      "ಶಾಂತ ಸಮಯ — ಆಳವಾದ ಚಿಂತನೆಗೆ ಸೂಕ್ತ.",
    ],
  },
  ml: {
    morning: [
      "സുപ്രഭാതം. ഇന്ന് എന്താണ് തുടങ്ങേണ്ടത്?",
      "നമസ്കാരം. ഇന്ന് എവിടെ നിന്ന് ആരംഭിക്കാം?",
    ],
    afternoon: [
      "നമസ്കാരം. ഇന്നത്തെ ലക്ഷ്യം എന്താണ്?",
      "ശുഭ ഉച്ച. എങ്ങനെ സഹായിക്കാം?",
    ],
    evening: [
      "ശുഭ സന്ധ്യ. ദിവസം എങ്ങനെയായിരുന്നു?",
      "നമസ്കാരം. ഇപ്പോൾ എന്ത് ചെയ്യാം?",
    ],
    night: [
      "രാത്രിയിലും ജോലിയോ? ഫലപ്രദമാക്കാം.",
      "ശാന്തമായ സമയം — ആഴത്തിലുള്ള ചിന്തയ്ക്ക് അനുയോജ്യം.",
    ],
  },
  mr: {
    morning: ["सुप्रभात. आज कशावर काम करूया?", "नमस्कार. दिवसाची सुरुवात कुठून करूया?"],
    afternoon: ["नमस्कार. आजचे मुख्य काम काय आहे?", "शुभ दुपार. कशात मदत करू?"],
    evening: ["शुभ संध्याकाळ. दिवस कसा गेला?", "नमस्कार. आता काय करूया?"],
    night: ["उशिरापर्यंत काम? चला उपयुक्त बनवूया.", "शांत वेळ — खोल विचारांसाठी उत्तम."],
  },
  gu: {
    morning: ["સુપ્રભાત. આજે શું શરૂ કરીએ?", "નમસ્તે. આજે કયા વિષય પર કામ કરીએ?"],
    afternoon: ["નમસ્તે. આજનું મુખ્ય કાર્ય શું છે?", "શુભ બપોર. કેવી રીતે મદદ કરું?"],
    evening: ["શુભ સાંજ. દિવસ કેવો રહ્યો?", "નમસ્તે. હવે શું કરીએ?"],
    night: ["મોડી રાત સુધી કામ? ચાલો ઉપયોગી બનાવીએ.", "શાંત સમય — ઊંડા વિચારો માટે યોગ્ય."],
  },
  pa: {
    morning: ["ਸ਼ੁਭ ਸਵੇਰ। ਅੱਜ ਕੀ ਸ਼ੁਰੂ ਕਰੀਏ?", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ। ਅੱਜ ਕਿਸ ਗੱਲ 'ਤੇ ਕੰਮ ਕਰੀਏ?"],
    afternoon: ["ਸਤ ਸ੍ਰੀ ਅਕਾਲ। ਅੱਜ ਦਾ ਮੁੱਖ ਕੰਮ ਕੀ ਹੈ?", "ਸ਼ੁਭ ਦੁਪਹਿਰ। ਕਿਵੇਂ ਮਦਦ ਕਰਾਂ?"],
    evening: ["ਸ਼ੁਭ ਸ਼ਾਮ। ਦਿਨ ਕਿਵੇਂ ਰਿਹਾ?", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ। ਹੁਣ ਕੀ ਕਰੀਏ?"],
    night: ["ਦੇਰ ਰਾਤ ਤੱਕ ਕੰਮ? ਆਓ ਇਸ ਨੂੰ ਲਾਭਦਾਇਕ ਬਣਾਈਏ।", "ਸ਼ਾਂਤ ਸਮਾਂ — ਡੂੰਘੀ ਸੋਚ ਲਈ ਢੁਕਵਾਂ।"],
  },
  bn: {
    morning: ["সুপ্রভাত। আজ কী নিয়ে শুরু করব?", "নমস্কার। আজ কোন বিষয়ে কাজ করব?"],
    afternoon: ["নমস্কার। আজকের প্রধান কাজ কী?", "শুভ অপরাহ্ন। কীভাবে সাহায্য করব?"],
    evening: ["শুভ সন্ধ্যা। দিন কেমন কাটল?", "নমস্কার। এখন কী করব?"],
    night: ["রাত অবধি কাজ? চলুন কার্যকর করি।", "শান্ত সময় — গভীর চিন্তার জন্য উপযুক্ত।"],
  },
  or: {
    morning: ["ଶୁଭ ପ୍ରଭାତ। ଆଜି କଣ ଆରମ୍ଭ କରିବା?", "ନମସ୍କାର। ଆଜି କେଉଁଠାରୁ ଆରମ୍ଭ କରିବା?"],
    afternoon: ["ନମସ୍କାର। ଆଜିର ମୁଖ୍ୟ କାର୍ଯ୍ୟ କଣ?", "ଶୁଭ ମଧ୍ୟାହ୍ନ। କିପରି ସାହାଯ୍ୟ କରିବି?"],
    evening: ["ଶୁଭ ସନ୍ଧ୍ୟା। ଦିନ କେମିତି ଥିଲା?", "ନମସ୍କାର। ବର୍ତ୍ତମାନ କଣ କରିବା?"],
    night: ["ରାତି ପର୍ଯ୍ୟନ୍ତ କାର୍ଯ୍ୟ? ଚାଲନ୍ତୁ ଫଳପ୍ରଦ କରିବା।", "ଶାନ୍ତ ସମୟ — ଗଭୀର ଚିନ୍ତା ପାଇଁ ଉପଯୁକ୍ତ।"],
  },
  as: {
    morning: ["শুভ প্ৰভাত। আজি কি আৰম্ভ কৰিম?", "নমস্কাৰ। আজি কোন বিষয়ত কাম কৰিম?"],
    afternoon: ["নমস্কাৰ। আজিৰ মূল কাম কি?", "শুভ দুপৰীয়া। কেনেকৈ সহায় কৰিম?"],
    evening: ["শুভ সন্ধিয়া। দিনটো কেনেকুৱা আছিল?", "নমস্কাৰ। এতিয়া কি কৰিম?"],
    night: ["ৰাতিলৈকে কাম? আহক ফলপ্ৰসূ কৰোঁ।", "শান্ত সময় — গভীৰ চিন্তাৰ বাবে উপযোগী।"],
  },
  ur: {
    morning: ["صبح بخیر۔ آج کس چیز پر کام کریں؟", "السلام علیکم۔ دن کا آغاز کہاں سے کریں؟"],
    afternoon: ["السلام علیکم۔ آج کا اہم کام کیا ہے؟", "بعد از دوپہر۔ کیسے مدد کروں؟"],
    evening: ["شام بخیر۔ دن کیسا رہا؟", "السلام علیکم۔ اب کیا کریں؟"],
    night: ["دیر رات تک کام؟ اسے مفید بناتے ہیں۔", "پرسکون وقت — گہرے سوچ کے لیے موزوں۔"],
  },
  sa: {
    morning: ["सुप्रभातम्। अद्य किं आरभेम?", "नमस्ते। अद्य कस्मिन् विषये कार्यं कुर्मः?"],
    afternoon: ["नमस्ते। अद्यस्य मुख्यं कार्यं किम्?", "शुभ मध्याह्नः। कथं साहाय्यं करोमि?"],
    evening: ["शुभ सायम्। दिनं कीदृशं आसीत्?", "नमस्ते। इदानीं किं कुर्मः?"],
    night: ["रात्रौ अपि कार्यम्? सफलं कुर्मः।", "शान्तः कालः — गम्भीरचिन्तनाय योग्यः।"],
  },
  ne: {
    morning: ["शुभ प्रभात। आज केमा काम गरौं?", "नमस्कार। दिनको सुरुवात कहाँबाट गरौं?"],
    afternoon: ["नमस्कार। आजको मुख्य काम के हो?", "शुभ दिउँसो। कसरी सहयोग गरूँ?"],
    evening: ["शुभ साँझ। दिन कस्तो रह्यो?", "नमस्कार। अब के गरौं?"],
    night: ["राति सम्म काम? यसलाई उपयोगी बनाऔं।", "शान्त समय — गहिरो सोचका लागि उपयुक्त।"],
  },
  mai: {
    morning: ["सुप्रभात। आइ की सँ शुरू करी?", "प्रणाम। आइ कोन विषय पर काज करी?"],
    afternoon: ["प्रणाम। आइक मुख्य काज की अछि?", "शुभ दुपहरिया। कोना मदद करी?"],
    evening: ["शुभ सन्ध्या। दिन कोना बीतल?", "प्रणाम। आब की करी?"],
    night: ["राति धरि काज? एकरा उपयोगी बनाबी।", "शान्त समय — गहन विचारक लेल उपयुक्त।"],
  },
  kok: {
    morning: ["सुप्रभात. आयज कितें सुरू करूंया?", "नमस्कार. आयज कशेर काम करूंया?"],
    afternoon: ["नमस्कार. आयचें मुखेल काम कितें?", "शुभ दनपार. कशी मदत करूं?"],
    evening: ["शुभ सांज. दीस कसो गेलो?", "नमस्कार. आतां कितें करूंया?"],
    night: ["रातभर काम? येयात उपयोगी करूंया.", "शांत वेळ — खोलीं विचारांक बरो."],
  },
  sd: {
    morning: ["صبح بخير. اڄ ڇا شروع ڪريون؟", "سلام. اڄ ڪهڙي شيءِ تي ڪم ڪريون؟"],
    afternoon: ["سلام. اڄ جو مکيه ڪم ڇا آهي؟", "منجهند جو سلام. ڪيئن مدد ڪريان؟"],
    evening: ["شام بخير. ڏينهن ڪيئن گذريو؟", "سلام. هاڻي ڇا ڪريون؟"],
    night: ["دير رات تائين ڪم؟ اچو ته سٺو ڪريون.", "خاموش وقت — گهري سوچ لاءِ موزون."],
  },
  ks: {
    morning: ["صُبُح بَخیر۔ اَز کیازِ شروع کرو؟", "آداب۔ اَز کَتہٕ پؠٹھ کٲم کرو؟"],
    afternoon: ["آداب۔ اَزُک اہم کٲم کیا چھُ؟", "دوپہر بخیر۔ کِنٕ مدد کَرہ؟"],
    evening: ["شام بخیر۔ دۄہ کیتھ پاٹھؠ گَو؟", "آداب۔ ہٕنٛدَر کیازِ کرو؟"],
    night: ["گَٹھ رات تام کٲم؟ ییہِ فائدہ مَند بناوَو۔", "خاموش وَقت — گہرَ سوچَس خٲطرٕ مناسب۔"],
  },
  doi: {
    morning: ["सुप्रभात। अज्ज केह् शुरू करचै?", "नमस्ते। अज्ज केह् उप्पर कम्म करचै?"],
    afternoon: ["नमस्ते। अज्जदा मुक्ख कम्म केह् ऐ?", "शुभ दुपहरिया। किंयां मदत करां?"],
    evening: ["शुभ सांझ। दिन किंयां रैहा?", "नमस्ते। हुण केह् करचै?"],
    night: ["राती तगर कम्म? इसनूं उपयोगी बनाचै।", "शांत बेला — गहरी सोच लेई ठीक।"],
  },
  mni: {
    morning: ["ꯑꯌꯨꯛ ꯅꯨꯡꯉꯥꯏꯖꯔꯤ꯫ ꯉꯁꯤ ꯀꯔꯤ ꯍꯧꯒꯅꯤ?", "ꯈꯨꯔꯨꯝꯖꯔꯤ꯫ ꯉꯁꯤ ꯀꯔꯤꯗꯥ ꯊꯕꯛ ꯇꯧꯒꯅꯤ?"],
    afternoon: ["ꯈꯨꯔꯨꯝꯖꯔꯤ꯫ ꯉꯁꯤꯒꯤ ꯃꯔꯨꯑꯣꯏꯕ ꯊꯕꯛ ꯀꯔꯤꯅꯣ?", "ꯅꯨꯃꯤꯗꯥꯡ ꯅꯨꯡꯉꯥꯏꯖꯔꯤ꯫ ꯀꯃꯅ ꯃꯇꯦꯡ ꯄꯥꯡꯒꯅꯤ?"],
    evening: ["ꯅꯨꯃꯤꯗꯥꯡꯋꯥꯏꯔꯝ ꯅꯨꯡꯉꯥꯏꯖꯔꯤ꯫ ꯅꯨꯃꯤꯠ ꯀꯔꯝꯅ ꯂꯩꯈꯤ?", "ꯈꯨꯔꯨꯝꯖꯔꯤ꯫ ꯍꯧꯖꯤꯛ ꯀꯔꯤ ꯇꯧꯒꯅꯤ?"],
    night: ["ꯑꯍꯤꯡ ꯑꯣꯏꯕ ꯊꯕꯛ? ꯀꯥꯟꯅꯕ ꯑꯣꯏꯍꯅꯒꯅꯤ꯫", "ꯇꯨꯃꯤꯟꯅ ꯃꯇꯝ — ꯂꯨꯅ ꯋꯥꯈꯜꯂꯣꯟꯒꯤꯗꯃꯛ ꯃꯄꯨꯡ ꯐꯥꯅ꯫"],
  },
  sat: {
    morning: ["ᱥᱮᱫᱟᱭ ᱛᱟᱦᱮᱸᱸ᱾ ᱛᱮᱦᱮᱧ ᱪᱮᱫ ᱮᱛᱦᱚᱵ ᱠᱟᱱᱟ?", "ᱡᱚᱦᱟᱨ᱾ ᱛᱮᱦᱮᱧ ᱪᱮᱫ ᱨᱮᱭᱟᱜ ᱠᱟᱹᱢᱤ ᱠᱟᱱᱟ?"],
    afternoon: ["ᱡᱚᱦᱟᱨ᱾ ᱛᱮᱦᱮᱧᱟᱜ ᱢᱩᱬᱩᱛ ᱠᱟᱹᱢᱤ ᱪᱮᱫ ᱠᱟᱱᱟ?", "ᱥᱤᱧ ᱛᱟᱦᱮᱸᱸ᱾ ᱪᱮᱠᱟᱛᱮ ᱜᱚᱲᱚ ᱮᱢ ᱠᱟᱱᱟᱹ?"],
    evening: ["ᱟᱭᱩᱵ ᱛᱟᱦᱮᱸᱸ᱾ ᱢᱟᱦᱟᱸ ᱚᱠᱟ ᱞᱮᱠᱟ ᱛᱟᱦᱮᱸᱸ?", "ᱡᱚᱦᱟᱨ᱾ ᱱᱤᱛᱚᱜ ᱪᱮᱫ ᱠᱟᱱᱟᱹ?"],
    night: ["ᱧᱤᱫᱟᱹ ᱦᱟᱵᱤᱡ ᱠᱟᱹᱢᱤ? ᱰᱟᱦᱮ ᱠᱟᱹᱢᱤ ᱛᱮᱭᱟᱨ ᱮᱢᱟᱭ᱾", "ᱟᱡᱟᱹᱨ ᱚᱠᱛᱚ — ᱡᱚᱛᱚ ᱡᱟᱹᱛ ᱩᱨᱩᱢ ᱞᱟᱹᱜᱤᱫ ᱵᱮᱥ᱾"],
  },
  brx: {
    morning: ["गोसो साबखांथाय। दिनै मा मानी हाबाब मानो?", "जोहार। दिनै बे विषयनि सिङाव हाबाब मानो?"],
    afternoon: ["जोहार। दिनै आननि गाहाय हाबाब मा?", "साम साबखांथाय। बेसेबां हेफाजाब होगोन?"],
    evening: ["आगान साबखांथाय। सान बेसेबां जागायबाय?", "जोहार। दानो मा मानो?"],
    night: ["हरसिम सिम हाबाब? बेखौ मानसे खालामनानै लांगोन।", "आजाद समाव — गुमुर सानथाइनि थाखाय ठिक।"],
  },
};

const RECENCY_KEY = "sevens.greeting.recency";
const RECENCY_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;

type RecencyEntry = { key: string; ts: number };

function readRecency(): RecencyEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(RECENCY_KEY);
    if (!raw) return [];
    const now = Date.now();
    const parsed = JSON.parse(raw) as RecencyEntry[];
    return parsed.filter((e) => now - e.ts < RECENCY_WINDOW_MS);
  } catch {
    return [];
  }
}

function writeRecency(entries: RecencyEntry[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(RECENCY_KEY, JSON.stringify(entries.slice(-120)));
  } catch {
    /* ignore quota errors */
  }
}

export function pickGreeting(lang: LanguageCode, now = new Date()): string {
  const bucket = getTimeBucket(now);
  const set = GREETINGS[lang] ?? GREETINGS.en;
  const pool = set[bucket] ?? GREETINGS.en[bucket];
  const recent = new Set(readRecency().map((e) => e.key));

  const available = pool.filter((g) => !recent.has(`${lang}:${bucket}:${g}`));
  const source = available.length > 0 ? available : pool;
  const choice = source[Math.floor(Math.random() * source.length)];

  const next = readRecency();
  next.push({ key: `${lang}:${bucket}:${choice}`, ts: Date.now() });
  writeRecency(next);
  return choice;
}
