import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Language = "en" | "hi";

const STORAGE_KEY = "parakh-language";

const hindi: Record<string, string> = {
  "Skip to content": "मुख्य सामग्री पर जाएँ",
  "Back to home": "मुखपृष्ठ पर वापस जाएँ",
  "Investigator workspace": "अन्वेषक कार्यक्षेत्र",
  "Investigation workspace": "जाँच कार्यक्षेत्र",
  "source files in this case.": "स्रोत फ़ाइलें इस केस में हैं।",
  "case entries and your session entries; global chain verified server-side":
    "केस और आपके सत्र की प्रविष्टियाँ; वैश्विक श्रृंखला सर्वर पर सत्यापित",
  "Investigator sign-in": "अन्वेषक साइन इन",
  "Welcome to Parakh.": "परख में आपका स्वागत है।",
  "Sign in to your investigation server, or take a look around with the sample case.":
    "अपने जाँच सर्वर में साइन इन करें या नमूना केस देखें।",
  Username: "उपयोगकर्ता नाम",
  Password: "पासवर्ड",
  "Enter your username": "अपना उपयोगकर्ता नाम दर्ज करें",
  "Enter your password": "अपना पासवर्ड दर्ज करें",
  "Show password": "पासवर्ड दिखाएँ",
  "Hide password": "पासवर्ड छिपाएँ",
  "Sign in": "साइन इन",
  "Signing in…": "साइन इन हो रहा है…",
  "or explore first": "या पहले देखें",
  "View demo without signing in": "बिना साइन इन डेमो देखें",
  "No account needed. Explore fictional evidence in the offline sample workspace.":
    "खाते की आवश्यकता नहीं। ऑफ़लाइन नमूना कार्यक्षेत्र में काल्पनिक साक्ष्य देखें।",
  "Need access? Ask the person who manages your Parakh server for an investigator account.":
    "पहुँच चाहिए? परख सर्वर प्रबंधक से अन्वेषक खाता माँगें।",
  "One place to see the whole picture": "पूरी तस्वीर देखने का एक स्थान",
  "Parakh home": "परख मुखपृष्ठ",
  "Main navigation": "मुख्य नेविगेशन",
  "DIGITAL EVIDENCE INTELLIGENCE": "डिजिटल साक्ष्य विश्लेषण",
  "CLARITY THROUGH EVIDENCE": "साक्ष्य से स्पष्टता",
  "Follow the evidence.": "साक्ष्य का अनुसरण करें।",
  "Keep the context.": "संदर्भ बनाए रखें।",
  "Move between records, timelines and connections in one investigator workspace.":
    "एक ही कार्यक्षेत्र में रिकॉर्ड, समयरेखा और संबंध देखें।",
  "Self-hosted · Source-focused · Built for careful review":
    "स्व-होस्टेड · स्रोत-केंद्रित · सावधानीपूर्ण समीक्षा के लिए",
  "Photo credits": "चित्र श्रेय",
  "Digital investigations": "डिजिटल जाँच",
  "Parakh · Investigator access": "परख · अन्वेषक पहुँच",

  "Active Cases": "सक्रिय केस",
  "Active Cases | Parakh": "सक्रिय केस | परख",
  "Parakh | Digital evidence, connected": "परख | जुड़ा हुआ डिजिटल साक्ष्य",
  "Investigator sign-in | Parakh": "अन्वेषक साइन इन | परख",
  "Upload evidence | Parakh": "साक्ष्य अपलोड | परख",
  "Import report | Parakh": "आयात रिपोर्ट | परख",
  "Your active cases": "आपके सक्रिय केस",
  "Cases / Investigator workspace": "केस / अन्वेषक कार्यक्षेत्र",
  "Only cases permitted by your account and membership are listed.":
    "केवल आपके खाते और सदस्यता से अनुमत केस दिखाए गए हैं।",
  "New case": "नया केस",
  "Provision team account": "टीम खाता बनाएँ",
  "Provision an account": "खाता बनाएँ",
  "Account username": "खाता उपयोगकर्ता नाम",
  "Initial password": "प्रारंभिक पासवर्ड",
  "System role": "सिस्टम भूमिका",
  "Create account": "खाता बनाएँ",
  "Case / FIR number": "केस / एफआईआर संख्या",
  Status: "स्थिति",
  Evidence: "साक्ष्य",
  "Last activity · IST": "अंतिम गतिविधि · IST",
  "Your case role": "आपकी केस भूमिका",
  "Open case": "केस खोलें",
  "No active cases yet.": "अभी कोई सक्रिय केस नहीं है।",
  "Create a case, then upload the logical evidence exports.":
    "केस बनाएँ, फिर तार्किक साक्ष्य निर्यात अपलोड करें।",
  "Ask a case investigator or admin to add you as a member.":
    "किसी केस अन्वेषक या व्यवस्थापक से सदस्य के रूप में जोड़ने को कहें।",
  "Case record": "केस रिकॉर्ड",
  "FIR / case number": "एफआईआर / केस संख्या",
  "Police station / jurisdiction": "पुलिस थाना / क्षेत्राधिकार",
  "Offence type": "अपराध प्रकार",
  "Lead investigator": "मुख्य अन्वेषक",
  "Not supplied": "उपलब्ध नहीं",
  "Case number not supplied": "केस संख्या उपलब्ध नहीं",
  "Upload evidence": "साक्ष्य अपलोड करें",
  "Open case workspace": "केस कार्यक्षेत्र खोलें",
  "No evidence yet. Add your first file.": "अभी कोई साक्ष्य नहीं। पहली फ़ाइल जोड़ें।",
  "Logical exports only. Original uploaded bytes are preserved.":
    "केवल तार्किक निर्यात। मूल अपलोड की गई बाइट्स सुरक्षित रहती हैं।",
  "Case details are administrative records, not evidentiary findings. Changes are linked to the audit log.":
    "केस विवरण प्रशासनिक रिकॉर्ड हैं, साक्ष्यात्मक निष्कर्ष नहीं। परिवर्तन ऑडिट लॉग से जुड़े हैं।",
  "Case access": "केस पहुँच",
  "Choose an existing account": "मौजूदा खाता चुनें",
  "Choose an account": "खाता चुनें",
  "Select a lead": "मुख्य अन्वेषक चुनें",
  "Team account": "टीम खाता",
  "Case role": "केस भूमिका",
  "Add / update member": "सदस्य जोड़ें / अपडेट करें",
  "Team members and case roles": "टीम सदस्य और केस भूमिकाएँ",
  "Account role and case role both apply. Prosecutors are always read-only.":
    "खाता भूमिका और केस भूमिका दोनों लागू होती हैं। अभियोजक हमेशा केवल-पठन होते हैं।",
  "Audit log": "ऑडिट लॉग",
  "Show audit log": "ऑडिट लॉग दिखाएँ",
  "Hide audit log": "ऑडिट लॉग छिपाएँ",
  "Sign out": "साइन आउट",
  "Demo viewer · Read-only": "डेमो दर्शक · केवल पढ़ने योग्य",
  "Read-only demo": "केवल-पठन डेमो",
  "Loading cases…": "केस लोड हो रहे हैं…",
  "Back to Active Cases": "सक्रिय केस पर वापस जाएँ",
  "Toggle navigation": "नेविगेशन खोलें या बंद करें",
  "Return to sign-in": "साइन इन पर वापस जाएँ",
  "Source time": "स्रोत समय",
  "Synthetic demo data": "कृत्रिम डेमो डेटा",
  "Synthetic evidence pack · signed in": "कृत्रिम साक्ष्य पैक · साइन इन किया हुआ",
  "INVESTIGATION SUITE": "जाँच प्रणाली",
  "Investment scam complaint": "निवेश धोखाधड़ी शिकायत",
  "Chain broken": "श्रृंखला टूटी हुई",
  "Chain not verified": "श्रृंखला सत्यापित नहीं",
  "EVIDENCE": "साक्ष्य",
  "Upload → Review → Investigate": "अपलोड → समीक्षा → जाँच",
  "Local demo review session": "स्थानीय डेमो समीक्षा सत्र",
  "Authenticated case session": "प्रमाणित केस सत्र",
  "Synthetic demonstration": "कृत्रिम प्रदर्शन",
  "Source-linked investigation": "स्रोत-संबद्ध जाँच",
  "Uploaded case records": "अपलोड किए गए केस रिकॉर्ड",
  "Evidence & custody": "साक्ष्य और अभिरक्षा",
  "Timeline & Replay": "समयरेखा और पुनरावलोकन",
  "Authenticity & contradictions": "प्रामाणिकता और विरोधाभास",
  "Synthetic demo": "कृत्रिम डेमो",
  "Synthetic case review": "कृत्रिम केस समीक्षा",
  "Live case": "सक्रिय केस",
  files: "फ़ाइलें",
  records: "रिकॉर्ड",

  Overview: "अवलोकन",
  Explore: "खोजें",
  Comms: "संचार",
  Money: "धन प्रवाह",
  Authenticity: "प्रामाणिकता",
  Graph: "संबंध ग्राफ",
  Board: "साक्ष्य बोर्ड",
  Map: "मानचित्र",
  Timeline: "समयरेखा",
  Findings: "निष्कर्ष",
  Reports: "रिपोर्ट",
  "Case navigator": "केस नेविगेटर",
  "CASE NAVIGATOR": "केस नेविगेटर",
  ANALYSIS: "विश्लेषण",
  "REVIEW & OUTPUT": "समीक्षा और आउटपुट",
  "Search all records…": "सभी रिकॉर्ड खोजें…",
  "Global search": "वैश्विक खोज",
  Assistant: "सहायक",
  Time: "समय",
  "Chain verified": "श्रृंखला सत्यापित",
  Cases: "केस",
  "Evidence intake": "साक्ष्य ग्रहण",
  "Search & filter": "खोज और फ़िल्टर",
  "Report & export": "रिपोर्ट और निर्यात",
  "Investigation summary": "जाँच सारांश",
  "Your evidence. One investigation workspace.": "आपका साक्ष्य। एक जाँच कार्यक्षेत्र।",
  "Begin with evidence intake, inspect parsed records and document source-backed findings.":
    "साक्ष्य ग्रहण से शुरू करें, रिकॉर्ड जाँचें और स्रोत-समर्थित निष्कर्ष दर्ज करें।",
  "Explore evidence": "साक्ष्य खोजें",
  "Open investigation board": "जाँच बोर्ड खोलें",
  "Source distribution": "स्रोत वितरण",
  "Activity across sources": "स्रोतों में गतिविधि",
  "Evidence categories": "साक्ष्य श्रेणियाँ",
  "View all records": "सभी रिकॉर्ड देखें",
  Communications: "संचार",
  Transactions: "लेन-देन",
  Locations: "स्थान",
  Documents: "दस्तावेज़",
  "Items requiring attention": "ध्यान देने योग्य मदें",
  "Open findings workspace": "निष्कर्ष कार्यक्षेत्र खोलें",
  "Latest dated records": "नवीनतम दिनांकित रिकॉर्ड",
  "Questions & supporting evidence": "प्रश्न और सहायक साक्ष्य",
  "No scenario findings applied": "कोई परिदृश्य निष्कर्ष लागू नहीं",
  "Evidence coverage by source": "स्रोत के अनुसार साक्ष्य कवरेज",
  "Case exhibit tray": "केस प्रदर्श ट्रे",
  "Drop exhibits here": "प्रदर्श यहाँ रखें",
  "Save findings and tray": "निष्कर्ष और ट्रे सहेजें",
  "INVESTIGATION CONTROL CENTRE": "जाँच नियंत्रण केंद्र",
  "Follow the evidence. Resolve the discrepancies.": "साक्ष्य का अनुसरण करें। विसंगतियाँ सुलझाएँ।",
  "Review communications, trace recorded transfers and test the refund claim against its sources.":
    "संचार की समीक्षा करें, दर्ज लेन-देन का पता लगाएँ और स्रोतों से धनवापसी दावे की जाँच करें।",
  "INVESTIGATION WORKFLOW": "जाँच कार्यप्रवाह",
  "Originals & custody": "मूल फ़ाइलें और अभिरक्षा",
  "Analysis": "विश्लेषण",
  "Search & correlate": "खोजें और सहसंबंध बनाएँ",
  "Review": "समीक्षा",
  "Findings & exhibits": "निष्कर्ष और प्रदर्श",
  "Evidence files": "साक्ष्य फ़ाइलें",
  "Parsed source records · includes notices": "पार्स किए गए स्रोत रिकॉर्ड · सूचनाएँ शामिल",
  "Review findings": "निष्कर्षों की समीक्षा",
  "Verified": "सत्यापित",
  "Broken": "टूटा हुआ",
  "Unchecked": "जाँचा नहीं गया",
  "Simulated demo chain": "नमूना डेमो श्रृंखला",
  "Backend chain status": "बैकएंड श्रृंखला स्थिति",
  "EVIDENCE INTELLIGENCE": "साक्ष्य विश्लेषण",
  "SOURCE-LINKED RECORDS": "स्रोत-संबद्ध रिकॉर्ड",
  "Source-linked records": "स्रोत-संबद्ध रिकॉर्ड",
  "LOADED RECORDS": "लोड किए गए रिकॉर्ड",
  "Loaded records": "लोड किए गए रिकॉर्ड",
  "Counts reflect loaded records, including repeated representations. Select a source to inspect its evidence.":
    "गिनती में दोहराए गए रूपों सहित लोड रिकॉर्ड शामिल हैं। साक्ष्य देखने के लिए स्रोत चुनें।",
  "TEMPORAL ANALYSIS · IST": "समय विश्लेषण · IST",
  "No timestamped records are available.": "समय-मुद्रा वाले रिकॉर्ड उपलब्ध नहीं हैं।",
  "Other": "अन्य",
  "Daily activity; select a day to filter the evidence": "दैनिक गतिविधि; साक्ष्य फ़िल्टर करने के लिए दिन चुनें",
  "Select a day to inspect exact records. Proximity in time does not establish causation.":
    "सटीक रिकॉर्ड देखने के लिए दिन चुनें। समय की निकटता कारण सिद्ध नहीं करती।",
  "EXTRACTED CONTENT": "निकाली गई सामग्री",
  "Counts describe loaded records and can overlap across categories. Open a category to inspect its sources.":
    "गिनती लोड रिकॉर्ड दर्शाती है और श्रेणियों में दोहराव हो सकता है। स्रोत देखने के लिए श्रेणी खोलें।",
  "REVIEW DESK": "समीक्षा डेस्क",
  "Evidence review": "साक्ष्य समीक्षा",
  "Curated synthetic leads": "चयनित कृत्रिम सुराग",
  "Review the uploaded records before recording conclusions. No scenario leads have been applied.":
    "निष्कर्ष दर्ज करने से पहले अपलोड रिकॉर्ड की समीक्षा करें। कोई परिदृश्य सुराग लागू नहीं है।",
  "SOURCE CHRONOLOGY": "स्रोत कालक्रम",
  "Original source timestamps · IST. Order can depend on device-clock uncertainty.":
    "मूल स्रोत समय-मुद्राएँ · IST। क्रम उपकरण घड़ी की अनिश्चितता से प्रभावित हो सकता है।",
  "INVESTIGATIVE ASSESSMENT": "जाँच आकलन",
  "Review required": "समीक्षा आवश्यक",
  "Review uploaded sources before recording a conclusion. Automatic question answering for arbitrary cases is planned.":
    "निष्कर्ष दर्ज करने से पहले अपलोड स्रोतों की समीक्षा करें। अन्य केसों के लिए स्वचालित प्रश्नोत्तर नियोजित है।",
  "Open Explore": "खोज खोलें",
  "Counts include provenance notes and duplicate document representations. They are not independent corroboration.":
    "गिनती में स्रोत-इतिहास नोट और दस्तावेज़ों के दोहराए रूप शामिल हैं। वे स्वतंत्र पुष्टि नहीं हैं।",
  "Saved case review": "सहेजी गई केस समीक्षा",
  "Drag a source chip, record or finding into the tray. Save before exporting. Status is an investigator assessment; citations establish traceability.":
    "स्रोत चिप, रिकॉर्ड या निष्कर्ष को ट्रे में खींचें। निर्यात से पहले सहेजें। स्थिति अन्वेषक का आकलन है; उद्धरण स्रोत तक पहुँच सुनिश्चित करते हैं।",

  "Map & telecom": "मानचित्र और दूरसंचार",
  "LOCATION & TELECOM CONTEXT": "स्थान और दूरसंचार संदर्भ",
  "GPS trail, stay points and towers": "GPS मार्ग, ठहराव बिंदु और टावर",
  "Observed-time lens": "अवलोकित समय सीमा",
  "Numbered GPS sequence": "क्रमांकित GPS क्रम",
  "Recorded route": "रिकॉर्ड किया मार्ग",
  "Stay-point cluster": "ठहराव समूह",
  "Tower and coverage": "टावर और कवरेज",
  "Map legend": "मानचित्र संकेत",
  "Interactive street map showing GPS records, route, stay clusters and telecom towers":
    "GPS रिकॉर्ड, मार्ग, ठहराव समूह और दूरसंचार टावर दिखाने वाला इंटरैक्टिव मानचित्र",
  "Street basemap © OpenStreetMap contributors. Loading tiles sends the viewed area to the tile provider. Repeated records at one coordinate are fanned slightly so each receipt remains selectable. Tower circles show coverage context, not a precise handset location.":
    "सड़क आधार मानचित्र © OpenStreetMap योगदानकर्ता। टाइल लोड होने पर देखा गया क्षेत्र प्रदाता को भेजा जाता है। एक ही निर्देशांक के दोहराए रिकॉर्ड थोड़ा अलग दिखते हैं ताकि हर रसीद चुनी जा सके। टावर वृत्त कवरेज संदर्भ दिखाते हैं, सटीक हैंडसेट स्थान नहीं।",
  "zoom or drag the street map, then follow the numbered route from 1 to":
    "सड़क मानचित्र को ज़ूम या खींचें, फिर 1 से क्रमांकित मार्ग का अनुसरण करें:",
  "Select any GPS or tower marker to open its source receipt.":
    "स्रोत रसीद खोलने के लिए कोई GPS या टावर मार्कर चुनें।",
  "Being near each other does not prove being together.": "पास होना साथ होने का प्रमाण नहीं है।",
  "Tower observations describe coverage context, not precise handset location.":
    "टावर अवलोकन कवरेज संदर्भ बताते हैं, सटीक हैंडसेट स्थान नहीं।",
  "observations ·": "अवलोकन ·",
  "m radius": "मी त्रिज्या",
  "GPS points shown": "दिखाए गए GPS बिंदु",
  "Stay-point clusters": "ठहराव समूह",
  "Distinct towers": "अलग टावर",
  "Source receipts": "स्रोत रसीदें",
  "DBSCAN stay points": "DBSCAN ठहराव बिंदु",
  "Telecom and tower hops": "दूरसंचार और टावर क्रम",
  "Call records": "कॉल रिकॉर्ड",
  "Common numbers": "सामान्य नंबर",
  "Source receipt": "स्रोत रसीद",
  Reference: "संदर्भ",
  "Source timestamp": "स्रोत समय-मुद्रा",
  "Raw timestamp": "मूल समय-मुद्रा",
  "Owner / source": "स्वामी / स्रोत",
  Parser: "पार्सर",
  "Original record": "मूल रिकॉर्ड",
  "Adjacent events": "आस-पास की घटनाएँ",
  "Add source to exhibit tray": "स्रोत को प्रदर्श ट्रे में जोड़ें",
  "Close source details": "स्रोत विवरण बंद करें",

  "Signed in": "साइन इन किया हुआ",
  "Synthetic demo · Read-only": "कृत्रिम डेमो · केवल-पठन",
  "Evidence intake workflow": "साक्ष्य ग्रहण कार्यप्रवाह",
  "Acquisition context": "अधिग्रहण संदर्भ",
  "Seal & process": "सील और प्रक्रिया",
  "Review sealed evidence": "सीलबंद साक्ष्य की समीक्षा",
  "Seal the originals first.": "पहले मूल फ़ाइलों को सील करें।",
  "Record where the evidence came from, then hash and preserve every original before parsing starts.":
    "साक्ष्य कहाँ से आया, यह दर्ज करें; फिर पार्सिंग से पहले हर मूल फ़ाइल का हैश बनाकर सुरक्षित रखें।",
  "Synthetic demo data · Read-only.": "कृत्रिम डेमो डेटा · केवल-पठन।",
  "No files, owners, devices or audit entries are written in demo mode.":
    "डेमो मोड में कोई फ़ाइल, स्वामी, उपकरण या ऑडिट प्रविष्टि नहीं लिखी जाती।",
  "1. Acquisition context": "1. अधिग्रहण संदर्भ",
  "Case name": "केस का नाम",
  "Owner": "स्वामी",
  "Device": "उपकरण",
  "(optional)": "(वैकल्पिक)",
  "Who handed it over": "किसने सौंपा",
  "When received": "कब प्राप्त हुआ",
  "Acquisition method": "अधिग्रहण विधि",
  "Acquisition notes": "अधिग्रहण नोट्स",
  "Condition, handover context, export steps…": "स्थिति, हस्तांतरण संदर्भ, निर्यात चरण…",
  "2. Add files, folders or ZIP": "2. फ़ाइलें, फ़ोल्डर या ZIP जोड़ें",
  "Drop evidence here": "साक्ष्य यहाँ छोड़ें",
  "Files and folders are sealed individually. Safe ZIP members become separately hashed child evidence.":
    "फ़ाइलें और फ़ोल्डर अलग-अलग सील होते हैं। सुरक्षित ZIP सामग्री अलग हैश वाले सहायक साक्ष्य बनती है।",
  "Choose files or ZIP": "फ़ाइलें या ZIP चुनें",
  "Choose folder": "फ़ोल्डर चुनें",
  "Choose evidence files": "साक्ष्य फ़ाइलें चुनें",
  "Choose evidence folder": "साक्ष्य फ़ोल्डर चुनें",
  "ZIP paths, expansion size, member count and compression ratios are checked before import.":
    "आयात से पहले ZIP पथ, विस्तारित आकार, सामग्री संख्या और संपीड़न अनुपात जाँचे जाते हैं।",
  "Evidence list": "साक्ष्य सूची",
  "Use bundled 15-file pack": "साथ दिया गया 15-फ़ाइल पैक उपयोग करें",
  "No evidence added yet.": "अभी कोई साक्ष्य नहीं जोड़ा गया।",
  "Add the full source pack before starting import.": "आयात शुरू करने से पहले पूरा स्रोत पैक जोड़ें।",
  "Source type": "स्रोत प्रकार",
  "File note": "फ़ाइल नोट",
  "No device": "कोई उपकरण नहीं",
  "Hashing, sealing, parsing and indexing. Originals remain unchanged.":
    "हैश, सील, पार्स और इंडेक्स किया जा रहा है। मूल फ़ाइलें अपरिवर्तित रहेंगी।",
  "Every selected original is sealed. Review the evidence list before investigation.":
    "हर चयनित मूल फ़ाइल सीलबंद है। जाँच से पहले साक्ष्य सूची की समीक्षा करें।",
  "Complete the acquisition record and confirm each file before import.":
    "आयात से पहले अधिग्रहण रिकॉर्ड पूरा करें और हर फ़ाइल की पुष्टि करें।",
  "Loading…": "लोड हो रहा है…",
  "Open sample analysis": "नमूना विश्लेषण खोलें",
  "Review import report": "आयात रिपोर्ट की समीक्षा करें",
  "Importing…": "आयात हो रहा है…",
  "Confirm demo list": "डेमो सूची की पुष्टि करें",
  "Start import": "आयात शुरू करें",
  "Sealing sequence": "सीलिंग क्रम",
  "Hashing": "हैश बनाना",
  "Stored": "संग्रहीत",
  "Parsing & indexing": "पार्सिंग और इंडेक्सिंग",
  "SHA-256 and MD5 are computed as bytes stream into the vault.":
    "वॉल्ट में बाइट्स आते समय SHA-256 और MD5 की गणना होती है।",
  "The original is content-addressed and read-only; exact duplicates are rejected.":
    "मूल सामग्री-पते के साथ केवल-पठन रहती है; हूबहू प्रतियाँ अस्वीकार होती हैं।",
  "A background job extracts reviewable records. Cancel and retry remain available.":
    "पृष्ठभूमि प्रक्रिया समीक्षायोग्य रिकॉर्ड निकालती है। रद्द और पुनः प्रयास उपलब्ध रहते हैं।",
  "A matching hash proves the stored bytes are unchanged. It does not prove that the source is true.":
    "मेल खाता हैश बताता है कि संग्रहीत बाइट्स नहीं बदलीं। यह स्रोत की सत्यता सिद्ध नहीं करता।",
  "Back to evidence intake": "साक्ष्य ग्रहण पर वापस जाएँ",
  "Import report": "आयात रिपोर्ट",
  "Review what Parakh understood.": "परख द्वारा समझी गई सामग्री की समीक्षा करें।",
  "Counts show normalized events. Decisions stay visible until an investigator confirms how the source should be interpreted.":
    "गिनती सामान्यीकृत घटनाएँ दिखाती है। स्रोत की व्याख्या की पुष्टि होने तक निर्णय दिखाई देते हैं।",
  "Loading import report…": "आयात रिपोर्ट लोड हो रही है…",
  "files imported": "आयात की गई फ़ाइलें",
  "normalized events": "सामान्यीकृत घटनाएँ",
  "decisions or warnings": "निर्णय या चेतावनियाँ",
  "Decisions needed": "निर्णय आवश्यक",
  "Date order": "दिनांक क्रम",
  "Fix and re-parse": "सुधारें और फिर पार्स करें",
  "Files and event counts": "फ़ाइलें और घटना गिनती",
  "File": "फ़ाइल",
  "Detection": "पहचान",
  "Events": "घटनाएँ",
  "Pending": "लंबित",
  "Confirming records the review in the hash-chained audit log.":
    "पुष्टि करने पर समीक्षा हैश-श्रृंखलित ऑडिट लॉग में दर्ज होती है।",
  "Working…": "कार्य जारी…",
  "Confirm and continue": "पुष्टि कर आगे बढ़ें",
  "No location records found": "कोई स्थान रिकॉर्ड नहीं मिला",
  "Upload GPS history or tower records with coordinates to populate this view.":
    "यह दृश्य भरने के लिए निर्देशांकों सहित GPS इतिहास या टावर रिकॉर्ड अपलोड करें।",
  "How to read this:": "इसे कैसे पढ़ें:",
  "Move through the observed sequence, then open any marker to inspect its source receipt.":
    "देखे गए क्रम में आगे बढ़ें, फिर स्रोत रसीद देखने के लिए कोई मार्कर खोलें।",
  "Map time slider": "मानचित्र समय स्लाइडर",
  "Pin a source record to the Evidence Board or open a marker above to inspect its receipt.":
    "स्रोत रिकॉर्ड को साक्ष्य बोर्ड पर पिन करें या उसकी रसीद देखने के लिए ऊपर मार्कर खोलें।",
  "Pinned map record": "पिन किया गया मानचित्र रिकॉर्ड",
  "Pinned tower record": "पिन किया गया टावर रिकॉर्ड",
  "No tower sequence": "कोई टावर क्रम नहीं",
  "Unique call observations; select one to open its source receipt.":
    "विशिष्ट कॉल अवलोकन; स्रोत रसीद खोलने के लिए एक चुनें।",
  "status not supplied": "स्थिति उपलब्ध नहीं",
  "Map analysis could not be displayed": "मानचित्र विश्लेषण प्रदर्शित नहीं हो सका",
  "Retry map analysis": "मानचित्र विश्लेषण पुनः प्रयास करें",
  "Correlating uploaded location and telecom records…": "अपलोड किए गए स्थान और दूरसंचार रिकॉर्ड का सहसंबंध बनाया जा रहा है…",
  "Complainant GPS trail": "शिकायतकर्ता का GPS मार्ग",
  "Tower context": "टावर संदर्भ",

  "Evidence relationship board": "साक्ष्य संबंध बोर्ड",
  "A line on this board shows a relationship in the records, or a hypothesis. It does not prove involvement.":
    "इस बोर्ड की रेखा रिकॉर्ड में संबंध या एक परिकल्पना दिखाती है। यह संलिप्तता सिद्ध नहीं करती।",
  "Board tools": "बोर्ड उपकरण",
  "Undo": "पूर्ववत करें",
  "Redo": "फिर से करें",
  "Undo (Ctrl/Cmd+Z)": "पूर्ववत करें (Ctrl/Cmd+Z)",
  "Redo (Ctrl/Cmd+Y)": "फिर से करें (Ctrl/Cmd+Y)",
  "Sticky note": "स्टिकी नोट",
  "Draw string": "संबंध रेखा बनाएँ",
  "Zone": "क्षेत्र",
  "Connect these": "इन्हें जोड़ें",
  "Shortest path": "सबसे छोटा मार्ग",
  "Expand neighbours": "पड़ोसी विस्तार करें",
  "Find gaps": "कमियाँ खोजें",
  "Auto-arrange": "स्वतः व्यवस्थित करें",
  "Delete": "हटाएँ",
  "Time lens": "समय सीमा",
  "All times": "सभी समय",
  "Zoom in": "ज़ूम इन",
  "Zoom out": "ज़ूम आउट",
  "Infinite evidence canvas": "अनंत साक्ष्य कैनवास",
  "Board minimap": "बोर्ड लघु-मानचित्र",
  "Receipt": "रसीद",
  "Investigator note, not evidence": "अन्वेषक नोट, साक्ष्य नहीं",
  "PERSON": "व्यक्ति",
  "IDENTIFIER": "पहचानकर्ता",
  "MESSAGE": "संदेश",
  "BANK": "बैंक",
  "DOCUMENT": "दस्तावेज़",
  "CALL": "कॉल",
  "LOCATION": "स्थान",
  "NOTE": "नोट",
  not_established: "स्थापित नहीं",
  "cards ·": "कार्ड ·",
  "strings · seed": "संबंध · सीड",
  "board item(s) in tray": "बोर्ड आइटम ट्रे में",
  "Board hash": "बोर्ड हैश",
  "· updated by": "· अपडेटकर्ता",
  "Selection": "चयन",
  "Select cards with Ctrl/Cmd or Shift. Arrow keys move an unlocked focused card.":
    "Ctrl/Cmd या Shift से कार्ड चुनें। तीर कुंजियाँ खुले चयनित कार्ड को स्थानांतरित करती हैं।",
  "Send selected to exhibit tray": "चयनित सामग्री प्रदर्श ट्रे में भेजें",
  "Snapshots": "स्नैपशॉट",
  "Save named version": "नामित संस्करण सहेजें",
  "Gap leads": "कमी के सुराग",
  "Run Find gaps. Suggestions remain leads, never findings.": "कमियाँ खोजें चलाएँ। सुझाव सुराग हैं, निष्कर्ष नहीं।",
  "Output": "आउटपुट",
  "Caption": "शीर्षक-विवरण",
  "PDF report page": "PDF रिपोर्ट पृष्ठ",
  "not saved": "सहेजा नहीं गया",
  "planned [T3]": "नियोजित [T3]",
  "Realtime multi-user editing:": "रीयल-टाइम बहु-उपयोगकर्ता संपादन:",
  "Current edits are revision-checked and attributed individually.": "वर्तमान संपादन संस्करण-जाँचे और व्यक्तिगत रूप से संबद्ध हैं।",
  ". Current edits are revision-checked and attributed individually.": ". वर्तमान संपादन संस्करण-जाँचे और व्यक्तिगत रूप से संबद्ध हैं।",

  "Pages": "पृष्ठ",
  "Remove": "हटाएँ",
  "Finding statement": "निष्कर्ष कथन",
  "Supporting record": "सहायक रिकॉर्ड",
  "No support: not established": "कोई समर्थन नहीं: स्थापित नहीं",
  "Add finding": "निष्कर्ष जोड़ें",
  "Review state": "समीक्षा स्थिति",
  "Link selected record": "चयनित रिकॉर्ड जोड़ें",
  "Add to tray": "ट्रे में जोड़ें",
  "Notes": "नोट्स",
  "Tags (comma separated)": "टैग (अल्पविराम से अलग)",
  "Add comment": "टिप्पणी जोड़ें",
  "Page budget": "पृष्ठ सीमा",
  "Exhibit page budget": "प्रदर्श पृष्ठ सीमा",
  "Suggest minimum exhibits": "न्यूनतम प्रदर्श सुझाएँ",
  "Download cited report PDF": "उद्धरणयुक्त रिपोर्ट PDF डाउनलोड करें",
  established: "स्थापित",
  possible: "संभावित",
  "not established": "स्थापित नहीं",
  contradicted: "खंडित",
  draft: "मसौदा",
  reviewing: "समीक्षाधीन",
  reviewed: "समीक्षित",

  "Bring every source together": "हर स्रोत को एक साथ लाएँ",
  "Find the meaningful detail": "महत्वपूर्ण विवरण खोजें",
  "Check what has changed": "देखें क्या बदला है",
  "Examine the inconsistencies": "विसंगतियों की जाँच करें",
  "Connect the evidence": "साक्ष्य जोड़ें",
  "Reconstruct the sequence": "घटनाक्रम पुनर्निर्मित करें",
  Capabilities: "क्षमताएँ",
  "How it works": "यह कैसे काम करता है",
  "The workspace": "कार्यक्षेत्र",
  "Our approach": "हमारा दृष्टिकोण",
  Menu: "मेनू",
  Close: "बंद करें",
  "Every trace.": "हर सुराग।",
  "A clearer": "अधिक स्पष्ट",
  "picture.": "चित्र।",
  "A clearer picture.": "एक स्पष्ट तस्वीर।",
  "Scattered records. Connected context. A focused workspace to examine digital evidence and explain the story it supports.":
    "बिखरे रिकॉर्ड। जुड़ा संदर्भ। डिजिटल साक्ष्य जाँचने और उससे समर्थित कहानी समझाने के लिए एक केंद्रित कार्यक्षेत्र।",
  "Evidence first. Uncertainty visible. Sources within reach.": "साक्ष्य पहले। अनिश्चितता स्पष्ट। स्रोत आसानी से उपलब्ध।",
  "Open investigator workspace": "अन्वेषक कार्यक्षेत्र खोलें",
  "Explore the demo": "डेमो देखें",
  "MANY SOURCES.": "कई स्रोत।",
  "ONE WORKSPACE.": "एक कार्यक्षेत्र।",
  "Chats & emails": "चैट और ईमेल",
  "Bank records": "बैंक रिकॉर्ड",
  "PDFs & images": "PDF और चित्र",
  "Browser history": "ब्राउज़र इतिहास",
  "Location & calls": "स्थान और कॉल",
  "Evidence sources": "साक्ष्य स्रोत",
  "PURPOSE-BUILT FOR INVESTIGATION": "जाँच के लिए विशेष रूप से निर्मित",
  "Less scattered evidence.": "कम बिखरा साक्ष्य।",
  "More informed decisions.": "अधिक सूचित निर्णय।",
  "Move from individual records to a connected account, with the supporting evidence close at hand.":
    "अलग-अलग रिकॉर्ड से एक जुड़ा विवरण बनाएँ, और सहायक साक्ष्य पास रखें।",
  "Start with logical exports: chats, bank statements, call records, documents and location history.":
    "चैट, बैंक विवरण, कॉल रिकॉर्ड, दस्तावेज़ और स्थान इतिहास जैसे तार्किक निर्यात से शुरू करें।",
  "Search & exploration": "खोज और अन्वेषण",
  "Search across records, narrow the context and return to the original file behind a result.":
    "रिकॉर्ड में खोजें, संदर्भ सीमित करें और परिणाम के पीछे की मूल फ़ाइल पर लौटें।",
  "Integrity & provenance": "अखंडता और स्रोत-इतिहास",
  "Authenticity review": "प्रामाणिकता समीक्षा",
  "Review file hashes and custody history. Unchanged since sealing does not mean a record is true.":
    "फ़ाइल हैश और अभिरक्षा इतिहास जाँचें। सीलिंग के बाद अपरिवर्तित होना रिकॉर्ड की सत्यता नहीं बताता।",
  "Compare a document with other records, review suspicious signals and keep alternative explanations visible.":
    "दस्तावेज़ की अन्य रिकॉर्ड से तुलना करें, संदिग्ध संकेत जाँचें और वैकल्पिक व्याख्याएँ दिखाई रखें।",
  "Graph & investigation board": "ग्राफ और जाँच बोर्ड",
  "Explore people, identifiers and transfers. Bring cited records onto a visual investigation board.":
    "लोगों, पहचानकर्ताओं और लेन-देन को खोजें। उद्धृत रिकॉर्ड दृश्य जाँच बोर्ड पर लाएँ।",
  "Timeline & replay": "समयरेखा और पुनरावलोकन",
  "Build a source-linked timeline, inspect clock uncertainty and replay the sequence for review.":
    "स्रोत-संबद्ध समयरेखा बनाएँ, घड़ी की अनिश्चितता जाँचें और समीक्षा के लिए क्रम दोहराएँ।",
  "THE HUMAN SIDE OF DIGITAL INVESTIGATION": "डिजिटल जाँच का मानवीय पक्ष",
  "BETTER CONTEXT. BETTER QUESTIONS.": "बेहतर संदर्भ। बेहतर प्रश्न।",
  "Behind every record,": "हर रिकॉर्ड के पीछे,",
  "a question worth asking.": "एक महत्वपूर्ण प्रश्न।",
  "Give the investigator room to compare, challenge and connect. Parakh brings the records into one working space, while keeping judgement with the person reviewing them.":
    "अन्वेषक को तुलना, प्रश्न और संबंध बनाने की जगह दें। परख रिकॉर्ड को एक कार्यस्थल में लाता है और निर्णय समीक्षक के पास रखता है।",
  "See the workspace": "कार्यक्षेत्र देखें",
  "A CLEAR PATH THROUGH THE CASE": "केस में स्पष्ट मार्ग",
  "Start with the source.": "स्रोत से शुरू करें।",
  "Finish with a supported account.": "समर्थित विवरण पर समाप्त करें।",
  "Start an investigation": "जाँच शुरू करें",
  "Upload & seal": "अपलोड और सील",
  "Explore & connect": "खोजें और जोड़ें",
  "Test & reconstruct": "परीक्षण और पुनर्निर्माण",
  "Review & explain": "समीक्षा और व्याख्या",
  "Create a case. Add the owner and acquisition context, upload your evidence, then review the import report.":
    "केस बनाएँ। स्वामी और अधिग्रहण संदर्भ जोड़ें, साक्ष्य अपलोड करें और आयात रिपोर्ट जाँचें।",
  "Search the records, follow the money and connect sources on the graph or investigation board.":
    "रिकॉर्ड खोजें, धन प्रवाह का अनुसरण करें और स्रोतों को ग्राफ या जाँच बोर्ड पर जोड़ें।",
  "Compare conflicting records, examine document signals and review the sequence with clock uncertainty.":
    "विरोधी रिकॉर्ड की तुलना करें, दस्तावेज़ संकेत जाँचें और घड़ी की अनिश्चितता सहित क्रम की समीक्षा करें।",
  "Record findings with their status and citations. Assemble exhibits and export a reviewable account.":
    "निष्कर्षों को स्थिति और उद्धरण सहित दर्ज करें। प्रदर्श इकट्ठा करें और समीक्षायोग्य विवरण निर्यात करें।",
  "ONE CASE. MULTIPLE PERSPECTIVES.": "एक केस। अनेक दृष्टिकोण।",
  "See the context.": "संदर्भ देखें।",
  "Inspect the detail.": "विवरण जाँचें।",
  "A workspace that keeps exploration and the original source in the same conversation.":
    "ऐसा कार्यक्षेत्र जो खोज और मूल स्रोत को एक ही संदर्भ में रखता है।",
  "Workspace previews": "कार्यक्षेत्र पूर्वावलोकन",
  Connections: "संबंध",
  "WORKSPACE VIEW": "कार्यक्षेत्र दृश्य",
  "/ WORKSPACE VIEW": "/ कार्यक्षेत्र दृश्य",
  "The detail is always within reach.": "विवरण हमेशा पहुँच में है।",
  "Review the source, its recorded time and the context around it. Follow a finding back to the records that support it.":
    "स्रोत, दर्ज समय और आसपास के संदर्भ की समीक्षा करें। निष्कर्ष से उसे समर्थन देने वाले रिकॉर्ड तक जाएँ।",
  "A sequence you can interrogate.": "एक क्रम जिसे आप परख सकते हैं।",
  "Put different records on one timeline. Examine the source timestamps and the uncertainty behind their order.":
    "अलग रिकॉर्ड एक समयरेखा पर रखें। स्रोत समय-मुद्राएँ और उनके क्रम की अनिश्चितता जाँचें।",
  "Follow the links. Keep the proof.": "संबंधों का अनुसरण करें। प्रमाण सुरक्षित रखें।",
  "Link conversations, accounts and records into a working picture. A connection is a lead to examine, never automatic proof.":
    "वार्तालाप, खातों और रिकॉर्ड को कार्यशील चित्र में जोड़ें। संबंध जाँचने योग्य सुराग है, स्वतः प्रमाण नहीं।",
  "Interface preview · Synthetic demonstration data": "इंटरफ़ेस पूर्वावलोकन · कृत्रिम प्रदर्शन डेटा",
  "Illustrative connection map · Not a case finding": "उदाहरण संबंध मानचित्र · केस निष्कर्ष नहीं",
  "Demo mode uses clearly labelled synthetic data. No sign-in required.":
    "डेमो मोड स्पष्ट रूप से चिह्नित कृत्रिम डेटा उपयोग करता है। साइन इन आवश्यक नहीं।",
  "BUILT AROUND THE WAY YOU WORK": "आपके कार्य-ढंग के अनुसार निर्मित",
  "Space to think.": "सोचने की जगह।",
  "Tools to follow through.": "आगे बढ़ने के उपकरण।",
  "From a first review to a supported account, keep the detail and the wider picture together.":
    "पहली समीक्षा से समर्थित विवरण तक, बारीकी और व्यापक चित्र साथ रखें।",
  "REVIEW TOGETHER": "साथ समीक्षा करें",
  "A place for careful collaboration.": "सावधानीपूर्ण सहयोग का स्थान।",
  "FIND THE CONTEXT": "संदर्भ खोजें",
  "Keep the working picture connected.": "कार्यशील चित्र जुड़ा रखें।",
  "DOCUMENT THE REASONING": "तर्क दर्ज करें",
  "Explain the account behind the records.": "रिकॉर्ड के पीछे का विवरण समझाएँ।",
  "Editorial stock photographs · Illustrations of review and research, not case evidence or endorsements.":
    "संपादकीय स्टॉक चित्र · समीक्षा और शोध के उदाहरण, केस साक्ष्य या समर्थन नहीं।",
  "Photo sources": "चित्र स्रोत",
  "CAREFUL EXAMINATION. CLEAR LIMITS.": "सावधानीपूर्ण जाँच। स्पष्ट सीमाएँ।",
  "DESIGNED TO BE QUESTIONED": "प्रश्न किए जाने के लिए निर्मित",
  "Confidence comes": "विश्वास आता है",
  "from showing your work.": "अपना कार्य दिखाने से।",
  "Useful evidence tools should make it easier to ask difficult questions, including questions about their own conclusions.":
    "उपयोगी साक्ष्य उपकरणों से कठिन प्रश्न पूछना आसान होना चाहिए, उनके अपने निष्कर्षों पर भी।",
  "Every claim needs a receipt.": "हर दावे को रसीद चाहिए।",
  "Follow a supported finding to its source. Missing support means “not established”.":
    "समर्थित निष्कर्ष से उसके स्रोत तक जाएँ। समर्थन न हो तो स्थिति ‘स्थापित नहीं’ है।",
  "Leads stay separate from findings.": "सुराग निष्कर्षों से अलग रहते हैं।",
  "Review reasons, caveats and uncertainty before drawing a conclusion.":
    "निष्कर्ष से पहले कारण, सीमाएँ और अनिश्चितता जाँचें।",
  "Integrity has a precise meaning.": "अखंडता का सटीक अर्थ है।",
  "A matching hash shows a file is unchanged since sealing. It does not prove it was truthful.":
    "मेल खाता हैश दिखाता है कि सीलिंग के बाद फ़ाइल नहीं बदली। यह उसकी सत्यता सिद्ध नहीं करता।",
  "THE NEXT STEP STARTS WITH YOUR EVIDENCE": "अगला चरण आपके साक्ष्य से शुरू होता है",
  "Bring clarity to": "स्पष्टता लाएँ",
  "your next investigation.": "अपनी अगली जाँच में।",
  "Open the investigator workspace, or explore a synthetic case": "अन्वेषक कार्यक्षेत्र खोलें या कृत्रिम केस देखें",
  "before bringing in your own source files.": "अपनी स्रोत फ़ाइलें लाने से पहले।",
  "Self-hosted prototype · Synthetic demo available": "स्व-होस्टेड प्रोटोटाइप · कृत्रिम डेमो उपलब्ध",
  "EXAMINE. CONNECT. SUBSTANTIATE.": "जाँचें। जोड़ें। पुष्ट करें।",
  "Digital evidence. A clearer perspective.": "डिजिटल साक्ष्य। अधिक स्पष्ट दृष्टिकोण।",
  "Built for thoughtful review": "विचारपूर्ण समीक्षा के लिए निर्मित",
  "Open the interactive demo": "इंटरैक्टिव डेमो खोलें",
  "View demo": "डेमो देखें",
  "Investigation prototype": "जाँच प्रोटोटाइप",
  investigator: "अन्वेषक",
  analyst: "विश्लेषक",
  prosecutor: "अभियोजक",
  admin: "व्यवस्थापक",
  open: "खुला",
};

function translateDynamic(value: string) {
  const direct = hindi[value];
  if (direct) return direct;
  const rules: Array<[RegExp, (...parts: string[]) => string]> = [
    [/^Open case (.+)$/, (title) => `केस खोलें: ${title}`],
    [/^(\d+) files$/, (count) => `${count} फ़ाइलें`],
    [/^(\d+) records$/, (count) => `${count} रिकॉर्ड`],
    [/^(\d+) source files in this case\.$/, (count) => `इस केस में ${count} स्रोत फ़ाइलें हैं।`],
    [/^(\d+) loaded records across (\d+) evidence files$/, (records, files) => `${files} साक्ष्य फ़ाइलों में ${records} लोड रिकॉर्ड`],
    [/^(\d+) cards · (\d+) strings · seed (.+)$/, (cards, strings, seed) => `${cards} कार्ड · ${strings} संबंध · सीड ${seed}`],
    [/^(\d+) board item\(s\) in tray$/, (count) => `ट्रे में ${count} बोर्ड आइटम`],
    [/^Board hash (.+) · updated by (.+)$/, (hash, person) => `बोर्ड हैश ${hash} · अपडेटकर्ता ${person}`],
    [/^Community (\d+)$/, (number) => `समुदाय ${number}`],
    [/^Pages for (.+)$/, (item) => `${item} के पृष्ठ`],
    [/^Use acquisition owner \((.+)\)$/, (owner) => `अधिग्रहण स्वामी उपयोग करें (${owner})`],
    [/^Remove (.+)$/, (item) => `${item} हटाएँ`],
    [/^Cancel (.+)$/, (item) => `${item} रद्द करें`],
    [/^Retry (.+)$/, (item) => `${item} पुनः प्रयास करें`],
    [/^Source receipts · (\d+) records$/, (count) => `स्रोत रसीदें · ${count} रिकॉर्ड`],
    [/^Up to (\d+)% of observed time$/, (count) => `अवलोकित समय का ${count}% तक`],
    [/^GPS record (\d+)(.*)$/, (count, rest) => `GPS रिकॉर्ड ${count}${rest}`],
    [/^(.+) · (investigator|analyst|prosecutor|admin)$/, (name, role) => `${name} · ${hindi[role] ?? role}`],
  ];
  for (const [pattern, replacement] of rules) {
    const match = value.match(pattern);
    if (match) return replacement(...match.slice(1));
  }
  return value;
}

type LanguageContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  text: (english: string) => string;
};

const LanguageContext = createContext<LanguageContextValue>({
  language: "en",
  setLanguage: () => undefined,
  text: (english) => english,
});

const originalText = new WeakMap<CharacterData, string>();
const renderedText = new WeakMap<CharacterData, string>();
const originalAttributes = new WeakMap<Element, Map<string, string>>();
const renderedAttributes = new WeakMap<Element, Map<string, string>>();
const translatedAttributes = ["aria-label", "placeholder", "title"];
let originalDocumentTitle = document.title;
let renderedDocumentTitle = document.title;

function localizeDocumentTitle(language: Language) {
  if (document.title !== renderedDocumentTitle && document.title !== originalDocumentTitle) {
    originalDocumentTitle = document.title;
  }
  const next = language === "hi" ? translateDynamic(originalDocumentTitle) : originalDocumentTitle;
  if (document.title !== next) document.title = next;
  renderedDocumentTitle = next;
}

function shouldIgnore(node: Node) {
  const parent = node.parentElement;
  return (
    !parent ||
    ["SCRIPT", "STYLE", "NOSCRIPT", "CODE", "PRE"].includes(parent.tagName) ||
    Boolean(parent.closest("[data-i18n-ignore]"))
  );
}

function replaceText(node: CharacterData, language: Language) {
  if (shouldIgnore(node) || !node.data.trim()) return;
  const previousRendered = renderedText.get(node);
  if (!originalText.has(node) || (node.data !== previousRendered && node.data !== originalText.get(node))) {
    originalText.set(node, node.data);
  }
  const original = originalText.get(node) ?? node.data;
  const leading = original.match(/^\s*/)?.[0] ?? "";
  const trailing = original.match(/\s*$/)?.[0] ?? "";
  const core = original.trim();
  const next = language === "hi" ? `${leading}${translateDynamic(core)}${trailing}` : original;
  if (node.data !== next) node.data = next;
  renderedText.set(node, next);
}

function replaceAttributes(element: Element, language: Language) {
  const originals = originalAttributes.get(element) ?? new Map<string, string>();
  const rendered = renderedAttributes.get(element) ?? new Map<string, string>();
  for (const attribute of translatedAttributes) {
    const current = element.getAttribute(attribute);
    if (current === null) continue;
    if (!originals.has(attribute) || (current !== rendered.get(attribute) && current !== originals.get(attribute))) {
      originals.set(attribute, current);
    }
    const original = originals.get(attribute) ?? current;
    const next = language === "hi" ? translateDynamic(original) : original;
    if (current !== next) element.setAttribute(attribute, next);
    rendered.set(attribute, next);
  }
  originalAttributes.set(element, originals);
  renderedAttributes.set(element, rendered);
}

function localizeTree(root: Node, language: Language) {
  if (root.nodeType === Node.TEXT_NODE) replaceText(root as CharacterData, language);
  if (root.nodeType === Node.ELEMENT_NODE) replaceAttributes(root as Element, language);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  let current = walker.nextNode();
  while (current) {
    if (current.nodeType === Node.TEXT_NODE) replaceText(current as CharacterData, language);
    else replaceAttributes(current as Element, language);
    current = walker.nextNode();
  }
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(() =>
    window.localStorage.getItem(STORAGE_KEY) === "hi" ? "hi" : "en",
  );

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, language);
    document.documentElement.lang = language;
    localizeDocumentTitle(language);
    localizeTree(document.documentElement, language);
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === "characterData") replaceText(mutation.target as CharacterData, language);
        else if (mutation.type === "attributes") replaceAttributes(mutation.target as Element, language);
        else mutation.addedNodes.forEach((node) => localizeTree(node, language));
      }
      localizeDocumentTitle(language);
    });
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: translatedAttributes,
    });
    return () => observer.disconnect();
  }, [language]);

  const value = useMemo(
    () => ({
      language,
      setLanguage,
      text: (english: string) => (language === "hi" ? translateDynamic(english) : english),
    }),
    [language],
  );
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  return useContext(LanguageContext);
}

export function LanguageToggle() {
  const { language, setLanguage } = useLanguage();
  return (
    <div className="language-toggle" role="group" aria-label="Language selection" data-i18n-ignore>
      <span>Language / भाषा</span>
      <button type="button" aria-pressed={language === "en"} onClick={() => setLanguage("en")}>
        English
      </button>
      <button type="button" lang="hi" aria-pressed={language === "hi"} onClick={() => setLanguage("hi")}>
        हिन्दी
      </button>
    </div>
  );
}
