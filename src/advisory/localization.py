"""
Deterministic Multilingual Advisory Localization Module.

Supports canonical agricultural advisory representations in English (en), Marathi (mr),
and Hindi (hi) without using uncontrolled LLMs.

Design Invariants:
1. Purely deterministic, human-verified templates linked to canonical rule_id.
2. English (en) is the canonical primary stored version.
3. Explicit metadata tracks translation readiness and status.
4. Fallback to English (en) for unsupported or unverified language requests.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class SupportedLanguage(str, Enum):
    """Supported language codes for agricultural advisories."""
    ENGLISH = "en"
    MARATHI = "mr"
    HINDI = "hi"


DEFAULT_LANGUAGE = SupportedLanguage.ENGLISH.value
ALL_SUPPORTED_LANGUAGES = [
    SupportedLanguage.ENGLISH.value,
    SupportedLanguage.MARATHI.value,
    SupportedLanguage.HINDI.value,
]


# Explicit language review & readiness status tracking
LANGUAGE_METADATA: Dict[str, Dict[str, str]] = {
    "en": {
        "name": "English",
        "native_name": "English",
        "status": "VERIFIED_PRIMARY",
        "readiness": "Production Ready",
    },
    "mr": {
        "name": "Marathi",
        "native_name": "मराठी",
        "status": "STRUCTURED_REVIEWED",
        "readiness": "Deterministic Templates Active",
    },
    "hi": {
        "name": "Hindi",
        "native_name": "हिन्दी",
        "status": "STRUCTURED_REVIEWED",
        "readiness": "Deterministic Templates Active",
    },
}


@dataclass(frozen=True)
class LocalizedRuleContent:
    """Localized templates for a specific rule."""
    title_template: str
    advisory_points_templates: List[str]
    what_is_happening_template: Optional[str] = None
    why_it_matters_template: Optional[str] = None
    timing_template: Optional[str] = None
    warnings_templates: Optional[List[str]] = None

    def format_what_is_happening(self, fmt_context: dict) -> str:
        if self.what_is_happening_template:
            return self.what_is_happening_template.format(**fmt_context)
        rainfall = fmt_context.get("rainfall_mm", 0.0)
        panchayat = fmt_context.get("panchayat_name", "Panchayat")
        return f"{rainfall:.1f} mm rainfall predicted for {panchayat}."

    def format_why_it_matters(self, fmt_context: dict) -> str:
        if self.why_it_matters_template:
            return self.why_it_matters_template.format(**fmt_context)
        return "Agronomic conditions evaluated and verified by local agricultural extension rules."

    def format_timing(self, fmt_context: dict) -> str:
        if self.timing_template:
            return self.timing_template.format(**fmt_context)
        return "Next 24 to 48 hours"

    def format_warnings(self, fmt_context: dict) -> List[str]:
        if self.warnings_templates:
            return [w.format(**fmt_context) for w in self.warnings_templates]
        return []


# =============================================================================
# DETERMINISTIC MULTILINGUAL RULE CATALOG (BY RULE_ID)
# =============================================================================
MULTILINGUAL_RULE_CATALOG: Dict[str, Dict[str, LocalizedRuleContent]] = {
    # 1. NO SIGNIFICANT RAINFALL
    "RAIN_NO_SIGNIFICANT_V1": {
        "en": LocalizedRuleContent(
            title_template="Dry Weather Advisory for {panchayat_name} - Routine Farm Management",
            advisory_points_templates=[
                "No significant rainfall expected ({rainfall_mm:.1f} mm). Continue routine irrigation scheduling based on soil moisture and crop water needs.",
                "Favorable window for scheduled intercultural operations, hand weeding, and standard field maintenance.",
                "Inspect irrigation channels, drip lines, and pumps for leaks to optimize water conservation.",
                "Regularly assess soil moisture depth in shallow-rooted and newly transplanted crops.",
            ],
            what_is_happening_template="{rainfall_mm:.1f} mm dry weather conditions predicted for {panchayat_name}.",
            why_it_matters_template="Dry weather provides optimal conditions for weeding and intercultural operations; requires proactive irrigation management.",
            timing_template="Next 24 to 48 hours",
            warnings_templates=[],
        ),
        "mr": LocalizedRuleContent(
            title_template="{panchayat_name} साठी कोरडे हवामान कृषी सल्ला - नियमित शेती व्यवस्थापन",
            advisory_points_templates=[
                "लक्षणीय पावसाची शक्यता नाही ({rainfall_mm:.1f} मिमी). जमिनीतील ओलावा व पिकांच्या गरजेनुसार नियमित सिंचन सुरू ठेवावे.",
                "आंतरमशागत, खुरपणी व नियमित शेतीकामांसाठी पोषक हवामान राहील.",
                "पाण्याचा अपव्यय टाळण्यासाठी ठिबक सिंचन, तुषार संच व पाईपलाईनची तपासणी करून गळती दुरुस्त करावी.",
                "उथळ मुळे असलेल्या व नवीन लागवड केलेल्या पिकांमधील ओलाव्याची नियमित पाहणी करावी.",
            ],
            what_is_happening_template="{panchayat_name} साठी {rainfall_mm:.1f} मिमी कोरड्या हवामानाचा अंदाज आहे.",
            why_it_matters_template="कोरड्या हवामानामुळे आंतरमशागत व शेतीकामे सुरळीत करता येतील; जमिनीतील ओलावा पाहून सिंचनाचे नियोजन आवश्यक आहे.",
            timing_template="पुढील २४ ते ४८ तास",
            warnings_templates=[],
        ),
        "hi": LocalizedRuleContent(
            title_template="{panchayat_name} के लिए शुष्क मौसम कृषि सलाह - सामान्य कृषि प्रबंधन",
            advisory_points_templates=[
                "उल्लेखनीय वर्षा की संभावना नहीं है ({rainfall_mm:.1f} मिमी)। मिट्टी की नमी और फसल की आवश्यकता के अनुसार नियमित सिंचाई जारी रखें।",
                "निराई-गुड़ाई और सामान्य कृषि कार्यों के लिए मौसम अनुकूल रहेगा।",
                "पानी की बचत के लिए ड्रिप सिंचाई और पाइपलाइनों की जांच कर लीकेज ठीक करें।",
                "उथली जड़ों वाली और नई रोपित फसलों में मिट्टी की नमी की नियमित निगरानी करें।",
            ],
            what_is_happening_template="{panchayat_name} के लिए {rainfall_mm:.1f} मिमी शुष्क मौसम का पूर्वानुमान है।",
            why_it_matters_template="शुष्क मौसम से निराई-गुड़ाई और कृषि कार्य आसान होंगे; आवश्यकतानुसार समय पर सिंचाई प्रबंधन करें।",
            timing_template="अगले 24 से 48 घंटे",
            warnings_templates=[],
        ),
    },

    # 2. VERY LIGHT RAINFALL
    "RAIN_VERY_LIGHT_V1": {
        "en": LocalizedRuleContent(
            title_template="Very Light Rainfall Advisory for {panchayat_name} - Standard Farm Operations",
            advisory_points_templates=[
                "Very light rainfall expected ({rainfall_mm:.1f} mm). Normal field activities and crop management may continue as planned.",
                "Check root-zone soil moisture before initiating supplemental irrigation cycles.",
                "Favorable conditions for routine nursery management, intercultural hoeing, and field scouting.",
                "Ensure harvested produce in open threshing yards is kept under protective tarpaulins if drizzle occurs.",
            ],
            what_is_happening_template="Very light rainfall ({rainfall_mm:.1f} mm) forecast for {panchayat_name}.",
            why_it_matters_template="Light drizzle maintains surface soil moisture without disrupting standard crop care activities.",
            timing_template="Next 24 to 48 hours",
            warnings_templates=[],
        ),
        "mr": LocalizedRuleContent(
            title_template="{panchayat_name} साठी अतिशय हलका पाऊस सल्ला - नियमित शेतीकामे",
            advisory_points_templates=[
                "अतिशय हलक्या पावसाची शक्यता ({rainfall_mm:.1f} मिमी). नियोजित शेतीकामे व पीक व्यवस्थापन सुरू ठेवता येईल.",
                "पुढील सिंचनाची पाळी देण्यापूर्वी पिकांच्या मुळांमधील ओलावा तपासावा.",
                "रोपवाटिका व्यवस्थापन व कीड-रोग सर्वेक्षणासाठी परिस्थिती अनुकूल आहे.",
                "खळ्यामध्ये उघड्यावर ठेवलेला शेतमाल पावसाच्या सरी आल्यास सुरक्षित झाकून ठेवावा.",
            ],
            what_is_happening_template="{panchayat_name} साठी अतिशय हलक्या पावसाचा ({rainfall_mm:.1f} मिमी) अंदाज आहे.",
            why_it_matters_template="हलक्या सरींमुळे जमिनीच्या वरच्या थरात ओलावा राहील, नियमित पीक व्यवस्थापन सुरू ठेवता येईल.",
            timing_template="पुढील २४ ते ४८ तास",
            warnings_templates=[],
        ),
        "hi": LocalizedRuleContent(
            title_template="{panchayat_name} के लिए बहुत हल्की वर्षा सलाह - सामान्य कृषि कार्य",
            advisory_points_templates=[
                "बहुत हल्की वर्षा की संभावना ({rainfall_mm:.1f} मिमी)। सामान्य कृषि कार्य और फसल प्रबंधन जारी रखा जा सकता है।",
                "अगली सिंचाई से पहले फसल के जड़ क्षेत्र में मिट्टी की नमी की जांच करें।",
                "नर्सरी प्रबंधन और कीट-रोग निगरानी के लिए मौसम उपयुक्त है।",
                "खलिहान में रखी कटी हुई फसल को बारिश की बूंदों से बचाने के लिए तिरपाल से ढकें।",
            ],
            what_is_happening_template="{panchayat_name} के लिए बहुत हल्की वर्षा ({rainfall_mm:.1f} मिमी) का पूर्वानुमान है।",
            why_it_matters_template="हल्की बूंदों से मिट्टी की ऊपरी सतह नम रहेगी, नियमित फसल प्रबंधन जारी रखा जा सकता है।",
            timing_template="अगले 24 से 48 घंटे",
            warnings_templates=[],
        ),
    },

    # 3. LIGHT RAINFALL
    "RAIN_LIGHT_V1": {
        "en": LocalizedRuleContent(
            title_template="Light Rainfall Advisory for {panchayat_name} - Soil Moisture & Spraying Precautions",
            advisory_points_templates=[
                "Light rainfall forecast ({rainfall_mm:.1f} mm). Postpone light surface irrigation until post-rain soil moisture is evaluated.",
                "Ensure field surface aeration and avoid excessive water stagnation around tender seedlings.",
                "Avoid routine foliar operations or dusting during active rainfall periods to prevent wash-off.",
                "Store harvested produce, crop residues, and farm inputs under secure, dry coverings.",
            ],
            what_is_happening_template="Light rainfall ({rainfall_mm:.1f} mm) forecast for {panchayat_name}.",
            why_it_matters_template="Showers replenish soil moisture; spraying should be avoided during showers to prevent chemical wash-off.",
            timing_template="Next 24 to 48 hours",
            warnings_templates=[],
        ),
        "mr": LocalizedRuleContent(
            title_template="{panchayat_name} साठी हलका पाऊस सल्ला - ओलावा व फवारणी खबरदारी",
            advisory_points_templates=[
                "हलक्या पावसाचा अंदाज ({rainfall_mm:.1f} मिमी). जमिनीतील ओलावा पाहूनच पुढील सिंचनाचे नियोजन करावे.",
                "कोवळ्या रोपांच्या मुळाशी पाणी साचू नये म्हणून शेतात योग्य निचरा राखावा.",
                "पाऊस सुरू असताना कोणतीही फवारणी करणे टाळावे, जेणेकरून औषध वाहून जाणार नाही.",
                "काढणी केलेला शेतमाल व खते कोरड्या आणि सुरक्षित जागी साठवावीत.",
            ],
            what_is_happening_template="{panchayat_name} साठी हलक्या पावसाचा ({rainfall_mm:.1f} मिमी) अंदाज आहे.",
            why_it_matters_template="पावसामुळे ओलावा वाढेल; रासायनिक औषधे वाहून जाण्याचा धोका असल्याने पाऊस असताना फवारणी टाळावी.",
            timing_template="पुढील २४ ते ४८ तास",
            warnings_templates=[],
        ),
        "hi": LocalizedRuleContent(
            title_template="{panchayat_name} के लिए हल्की वर्षा सलाह - नमी एवं छिड़काव सावधानी",
            advisory_points_templates=[
                "हल्की वर्षा का पूर्वानुमान ({rainfall_mm:.1f} मिमी)। वर्षा के बाद नमी देखकर ही अगली सिंचाई करें।",
                "कोमल पौधों के पास पानी जमा न होने दें और जल निकासी सुचारू रखें।",
                "वर्षा के दौरान पर्णीय छिड़काव न करें ताकि दवा बह न जाए।",
                "कटी हुई फसल एवं उर्वरकों को सूखे व सुरक्षित स्थान पर रखें।",
            ],
            what_is_happening_template="{panchayat_name} के लिए हल्की वर्षा ({rainfall_mm:.1f} मिमी) का पूर्वानुमान है।",
            why_it_matters_template="हल्की वर्षा से नमी मिलेगी; दवा बहने से बचाने के लिए वर्षा के समय छिड़काव न करें।",
            timing_template="अगले 24 से 48 घंटे",
            warnings_templates=[],
        ),
    },

    # 4. MODERATE RAINFALL
    "RAIN_MODERATE_V1": {
        "en": LocalizedRuleContent(
            title_template="Moderate Rainfall Advisory for {panchayat_name} - Drainage Preparedness & Irrigation Suspension",
            advisory_points_templates=[
                "Moderate rainfall forecast ({rainfall_mm:.1f} mm). Temporarily suspend all irrigation operations as rainfall will satisfy crop water demand.",
                "Inspect and clean field drainage channels to ensure free flow and prevent water stagnation in crop root zones.",
                "Postpone chemical spraying, broadcasting of fertilizers, and intercultural operations until the rainfall subsides.",
                "Move harvested grains and agricultural inputs into sheltered, elevated, moisture-free storage.",
            ],
            what_is_happening_template="Moderate rainfall ({rainfall_mm:.1f} mm) predicted for {panchayat_name}.",
            why_it_matters_template="Substantial rainfall meets crop water requirements; excessive moisture may cause water stagnation in heavy soils.",
            timing_template="Next 24 to 48 hours",
            warnings_templates=[
                "Suspend chemical spraying and fertilizer applications until rainfall ceases.",
            ],
        ),
        "mr": LocalizedRuleContent(
            title_template="{panchayat_name} साठी मध्यम पाऊस सल्ला - पाण्याचा निचरा व सिंचन स्थगिती",
            advisory_points_templates=[
                "मध्यम पावसाचा अंदाज ({rainfall_mm:.1f} मिमी). पिकांना पुरेसा पाऊस मिळणार असल्याने सर्व प्रकारची सिंचने तात्पुरती थांबवावीत.",
                "पिकांच्या मुळांशी पाणी साचून नुकसान होऊ नये म्हणून शेतातील पाण्याचे चर आणि पाट स्वच्छ करावेत.",
                "पाऊस संपेपर्यंत खते देणे, रासायनिक फवारणी आणि आंतरमशागतीची कामे पुढे ढकलावीत.",
                "काढणी केलेले धान्य व निविष्ठा सुरक्षित आणि उंच जागी साठवून ठेवाव्यात.",
            ],
            what_is_happening_template="{panchayat_name} साठी मध्यम पावसाचा ({rainfall_mm:.1f} मिमी) अंदाज आहे.",
            why_it_matters_template="पुरेशा पावसामुळे पिकांची गरज भागेल; भारी जमिनीत पाणी साचून पिके पिवळी पडण्याचा किंवा मुळे कुजण्याचा धोका संभवतो.",
            timing_template="पुढील २४ ते ४८ तास",
            warnings_templates=[
                "पाऊस सुरू असताना कोणतीही रासायनिक फवारणी अथवा खते देणे टाळावे.",
            ],
        ),
        "hi": LocalizedRuleContent(
            title_template="{panchayat_name} के लिए मध्यम वर्षा सलाह - जल निकासी एवं सिंचाई स्थगन",
            advisory_points_templates=[
                "मध्यम वर्षा का पूर्वानुमान ({rainfall_mm:.1f} मिमी)। वर्षा से फसल की जल मांग पूरी होगी, अतः सभी प्रकार की सिंचाई तुरंत रोकें।",
                "फसल की जड़ों में पानी जमा होने से रोकने के लिए खेत की जल निकासी नालियों को साफ रखें।",
                "उर्वरक का बुरकाव, कीटनाशक छिड़काव और निराई-गुड़ाई बारिश रुकने तक स्थगित रखें।",
                "कटे हुए अनाज और कृषि इनपुट को ऊंचे व सूखे स्थान पर सुरक्षित करें।",
            ],
            what_is_happening_template="{panchayat_name} के लिए मध्यम वर्षा ({rainfall_mm:.1f} मिमी) का पूर्वानुमान है।",
            why_it_matters_template="पर्याप्त वर्षा से फसल की जल मांग पूरी होगी; भारी मिट्टी में जलभराव से जड़ सड़न का खतरा हो सकता है।",
            timing_template="अगले 24 से 48 घंटे",
            warnings_templates=[
                "वर्षा के दौरान कीटनाशक छिड़काव और रासायनिक खाद का प्रयोग न करें।",
            ],
        ),
    },

    # 5. HEAVY RAINFALL
    "RAIN_HEAVY_V1": {
        "en": LocalizedRuleContent(
            title_template="Heavy Rainfall Warning for {panchayat_name} - Excess Water Drainage & Crop Protection",
            advisory_points_templates=[
                "Heavy rainfall forecast ({rainfall_mm:.1f} mm). Strictly suspend all irrigation and open field operations.",
                "Immediately open, clear, and deepen drainage furrows to discharge excess runoff and avoid severe root-zone waterlogging.",
                "Provide physical support or staking for standing vegetable crops, young orchards, and tall crops vulnerable to wind and heavy rain.",
                "Keep farm livestock sheltered indoors with clean drinking water and dry bedding away from low-lying areas.",
                "Do not allow standing water accumulation around tree basins and vegetable beds.",
            ],
            what_is_happening_template="Heavy rainfall warning ({rainfall_mm:.1f} mm) in effect for {panchayat_name}.",
            why_it_matters_template="Intense precipitation creates acute risk of field waterlogging, nutrient leaching, and physical crop lodging.",
            timing_template="Next 24 to 48 hours",
            warnings_templates=[
                "Strictly do not apply chemical fertilizers or pesticide sprays before heavy rainfall.",
            ],
        ),
        "mr": LocalizedRuleContent(
            title_template="{panchayat_name} साठी मुसळधार पाऊस इशारा - पाण्याचा जलद निचरा व पीक संरक्षण",
            advisory_points_templates=[
                "मुसळधार पावसाचा इशारा ({rainfall_mm:.1f} मिमी). शेतीतील सर्व सिंचन व उघड्यावरील कामे तातडीने बंद ठेवावीत.",
                "शेतात पाणी साचून पिके कुजणे टाळण्यासाठी मुख्य निचरा चर त्वरित मोकळे व रुंद करावेत.",
                "भाजीपाला, फळबागा व उंच वाढणाऱ्या पिकांना वारा व पावसामुळे लोळू नये म्हणून काठ्यांचा आधार द्यावा.",
                "जनावरांना सखल भागातून सुरक्षित, कोरड्या व निवारा असलेल्या गोठ्यात बांधावे.",
                "झाडांच्या बुंध्याभोवती व वाफ्यांमध्ये पाणी साचू देऊ नये.",
            ],
            what_is_happening_template="{panchayat_name} साठी मुसळधार पावसाचा इशारा ({rainfall_mm:.1f} मिमी) लागू करण्यात आला आहे.",
            why_it_matters_template="मुसळधार पावसामुळे शेतात पाणी साचणे, खते वाहून जाणे व पिके लोळण्याचा गंभीर धोका निर्माण होतो.",
            timing_template="पुढील २४ ते ४८ तास",
            warnings_templates=[
                "मुसळधार पावसापूर्वी कोणत्याही प्रकारची रासायनिक खते अथवा कीटकनाशके फवारू नयेत.",
            ],
        ),
        "hi": LocalizedRuleContent(
            title_template="{panchayat_name} के लिए भारी वर्षा चेतावनी - अतिरिक्त जल निकासी एवं फसल सुरक्षा",
            advisory_points_templates=[
                "भारी वर्षा की चेतावनी ({rainfall_mm:.1f} मिमी)। सभी प्रकार की सिंचाई और खुले खेत के काम तुरंत बंद रखें।",
                "खेत में पानी भरने से बचाने के लिए जल निकासी नालियों को तुरंत गहरा और साफ करें।",
                "सब्जियों और कमजोर पौधों को हवा व तेज बारिश से गिरने से बचाने के लिए सहारा दें।",
                "पशुओं को निचले इलाकों से हटाकर सुरक्षित, सूखे व हवादार शेड में रखें।",
                "फसलों और फलदार वृक्षों के थालों में पानी जमा न होने दें।",
            ],
            what_is_happening_template="{panchayat_name} के लिए भारी वर्षा ({rainfall_mm:.1f} मिमी) की चेतावनी प्रभावी है।",
            why_it_matters_template="भारी वर्षा से खेतों में जलभराव, पोषक तत्वों का रिसाव और फसलों के गिरने का गंभीर जोखिम है।",
            timing_template="अगले 24 से 48 घंटे",
            warnings_templates=[
                "भारी वर्षा से पहले रासायनिक उर्वरक या कीटनाशकों का प्रयोग कतई न करें।",
            ],
        ),
    },

    # 6. VERY HEAVY RAINFALL
    "RAIN_VERY_HEAVY_V1": {
        "en": LocalizedRuleContent(
            title_template="Very Heavy Rainfall Alert for {panchayat_name} - Emergency Drainage & Infrastructure Protection",
            advisory_points_templates=[
                "Very heavy rainfall forecast ({rainfall_mm:.1f} mm). Immediate precautionary action required across farm plots.",
                "Open all main drainage outlets and field ditches to prevent inundation and topsoil erosion.",
                "Completely halt all agricultural machinery operations, chemical applications, and manual field labor.",
                "Safeguard nursery sheds, polyhouses, farm machinery, and electric motor pumps by relocating them to higher ground.",
                "Ensure livestock are secured in well-sheltered, flood-safe structures with adequate dry fodder reserves.",
                "Avoid crossing or working in submerged fields until excess water has safely receded.",
            ],
            what_is_happening_template="Very heavy rainfall alert ({rainfall_mm:.1f} mm) issued for {panchayat_name}.",
            why_it_matters_template="Severe inundation and topsoil erosion risk; immediate emergency drainage must be maintained.",
            timing_template="Next 24 to 48 hours",
            warnings_templates=[
                "Halt all farm machinery and electric pump operations in inundated areas.",
            ],
        ),
        "mr": LocalizedRuleContent(
            title_template="{panchayat_name} साठी अति मुसळधार पाऊस सतर्कता - आपत्कालीन निचरा व शेत संरक्षण",
            advisory_points_templates=[
                "अति मुसळधार पावसाचा इशारा ({rainfall_mm:.1f} मिमी). शेतात तातडीने संरक्षक उपाययोजना कराव्यात.",
                "मातीची धूप व शेत जलमय होणे टाळण्यासाठी सर्व मुख्य आउटलेट व चर पूर्णपणे मोकळे करावेत.",
                "ट्रॅक्टर, कृषी यंत्रे, फवारणी व शेतमजुरांची कामे पूर्णपणे थांबवावीत.",
                "विद्युत मोटारी, पंप, अवजारे व नर्सरीचे साहित्य सुरक्षित उंच जागेवर हलवावे.",
                "जनावरांसाठी पूर-मुक्त निवारा व कोरड्या चाऱ्याची व्यवस्था करावी.",
                "पाणी ओसरेपर्यंत पुराच्या पाण्यात किंवा दलदलीत जाणे टाळावे.",
            ],
            what_is_happening_template="{panchayat_name} साठी अति मुसळधार पावसाची ({rainfall_mm:.1f} मिमी) सतर्कता जारी करण्यात आली आहे.",
            why_it_matters_template="शेतात पूरस्थिती निर्माण होणे व वरची सुपीक माती वाहून जाण्याचा धोका; तातडीने अतिरिक्त पाणी बाहेर काढावे.",
            timing_template="पुढील २४ ते ४८ तास",
            warnings_templates=[
                "पाणी साचलेल्या भागात विद्युत मोटारी व अवजारे सुरू ठेवणे टाळावे.",
            ],
        ),
        "hi": LocalizedRuleContent(
            title_template="{panchayat_name} के लिए अत्यंत भारी वर्षा अलर्ट - आपातकालीन जल निकासी एवं सुरक्षा",
            advisory_points_templates=[
                "अत्यंत भारी वर्षा का अलर्ट ({rainfall_mm:.1f} मिमी)। खेतों में तत्काल एहतियाती कदम उठाएं।",
                "खेतों में बाढ़ और मिट्टी के कटाव को रोकने के लिए सभी मुख्य नालों को खोलें।",
                "कृषि मशीनरी का संचालन, छिड़काव और मजदूरों के कार्य पूरी तरह रोक दें।",
                "मोटर पंप, कृषि उपकरण और नर्सरी को सुरक्षित व ऊंचे स्थान पर ले जाएं।",
                "पशुओं को बाढ़-सुरक्षित स्थानों पर रखें और सूखे चारे का प्रबंध रखें।",
                "पानी उतरने तक जलमग्न खेतों में जाने से बचें।",
            ],
            what_is_happening_template="{panchayat_name} के लिए अत्यंत भारी वर्षा ({rainfall_mm:.1f} मिमी) का अलर्ट जारी किया गया है।",
            why_it_matters_template="खेतों में भीषण जलभराव और उपजाऊ मिट्टी के कटाव का खतरा; तत्काल जल निकासी सुनिश्चित करें।",
            timing_template="अगले 24 से 48 घंटे",
            warnings_templates=[
                "जलभराव वाले क्षेत्रों में विद्युत मोटर और मशीनरी का संचालन तुरंत बंद करें।",
            ],
        ),
    },

    # 7. EXTREMELY HEAVY RAINFALL
    "RAIN_EXTREMELY_HEAVY_V1": {
        "en": LocalizedRuleContent(
            title_template="Extremely Heavy Rainfall Red Alert for {panchayat_name} - Flood & Safety Precautions",
            advisory_points_templates=[
                "Extremely heavy rainfall forecast ({rainfall_mm:.1f} mm). Prioritize life, livestock, and farm infrastructure safety.",
                "Keep all farm waterways, drainage canals, and field bund outlets completely unobstructed to mitigate flash waterlogging and soil loss.",
                "Secure livestock, machinery, power lines, and valuable farm assets in elevated, flood-proof shelters.",
                "Strictly suspend all agricultural, harvesting, and transport activities across low-lying fields and riparian zones.",
                "Monitor farm bunds, perimeter embankments, and village water bodies for integrity against breaching.",
            ],
            what_is_happening_template="Extremely heavy rainfall red alert ({rainfall_mm:.1f} mm) active for {panchayat_name}.",
            why_it_matters_template="Extreme flash flood and infrastructure damage hazard across low-lying agricultural zones.",
            timing_template="Next 24 to 48 hours",
            warnings_templates=[
                "Red Alert: Completely halt all agricultural operations and stay clear of water channels.",
            ],
        ),
        "mr": LocalizedRuleContent(
            title_template="{panchayat_name} साठी अत्यंत तीव्र मुसळधार पाऊस रेड अलर्ट - पूर व जीवरक्षण खबरदारी",
            advisory_points_templates=[
                "अत्यंत तीव्र मुसळधार पाऊस रेड अलर्ट ({rainfall_mm:.1f} मिमी). स्वतःचा, जनावरांचा व शेतीच्या मालमत्तेचा जीव वाचवण्यास सर्वोच्च प्राधान्य द्यावे.",
                "अचानक पूर येऊन जमीन खचणे टाळण्यासाठी शेतातील सर्व ओढे व पाण्याचे मार्ग पूर्ण मोकळे ठेवावेत.",
                "जनावरे, अवजारे व मौल्यवान साहित्य उंच व पक्क्या निवाऱ्यात हलवावे.",
                "नदीकाठच्या व सखल भागातील शेती, वाहतूक व काढणीची कामे पूर्ण बंद ठेवावीत.",
                "शेताचे बांध व तलावांची धूप/फुटणे यावर बारकाईने लक्ष ठेवावे.",
            ],
            what_is_happening_template="{panchayat_name} साठी अत्यंत तीव्र मुसळधार पावसाचा ({rainfall_mm:.1f} मिमी) रेड अलर्ट जारी करण्यात आला आहे.",
            why_it_matters_template="सखल शेतीक्षेत्रात अचानक पूर येणे व शेतीच्या मालमत्तेचे नुकसान होण्याचा अत्यंत गंभीर धोका.",
            timing_template="पुढील २४ ते ४८ तास",
            warnings_templates=[
                "रेड अलर्ट: सर्व शेतीकामे त्वरित थांबवा आणि पाण्याच्या प्रवाहापासून दूर राहा.",
            ],
        ),
        "hi": LocalizedRuleContent(
            title_template="{panchayat_name} के लिए अत्यधिक तीव्र वर्षा रेड अलर्ट - बाढ़ एवं सुरक्षा सावधानियां",
            advisory_points_templates=[
                "अत्यधिक तीव्र वर्षा का रेड अलर्ट ({rainfall_mm:.1f} मिमी)। जान-माल और पशुधन की सुरक्षा को सर्वोच्च प्राथमिकता दें।",
                "आकस्मिक जलभराव रोकने के लिए सभी जल मार्गों और नालियों को खुला रखें।",
                "पशुधन, पंप और महंगे उपकरणों को ऊंचे बाढ़-सुरक्षित स्थानों पर स्थानांतरित करें।",
                "निचले व नदी किनारे के खेतों में सभी कृषि और आवागमन गतिविधियां पूरी तरह बंद करें।",
                "खेत के मेड़ों और तालाबों की सुरक्षा की निरंतर निगरानी करें।",
            ],
            what_is_happening_template="{panchayat_name} के लिए अत्यधिक तीव्र वर्षा ({rainfall_mm:.1f} मिमी) का रेड अलर्ट प्रभावी है।",
            why_it_matters_template="निचले कृषि क्षेत्रों में आकस्मिक बाढ़ और बुनियादी ढांचे के नुकसान का अत्यंत गंभीर खतरा।",
            timing_template="अगले 24 से 48 घंटे",
            warnings_templates=[
                "रेड अलर्ट: सभी कृषि गतिविधियां तत्काल रोकें और जल धाराओं से दूर रहें।",
            ],
        ),
    },
}


def get_localized_rule_content(
    rule_id: str,
    language: str = DEFAULT_LANGUAGE,
) -> LocalizedRuleContent:
    """
    Retrieve deterministic localized rule content for a given rule_id and language code.
    Falls back gracefully to English ('en') if language is not supported.

    Args:
        rule_id: Canonical rule identifier (e.g. RAIN_MODERATE_V1).
        language: ISO language code ('en', 'mr', 'hi').

    Returns:
        LocalizedRuleContent with localized title and points templates.
    """
    clean_lang = str(language).lower().strip()
    if clean_lang not in ALL_SUPPORTED_LANGUAGES:
        logger.warning(
            f"[LOCALIZATION_FALLBACK] Unsupported language requested '{language}'. "
            f"Falling back to default '{DEFAULT_LANGUAGE}' for rule '{rule_id}'."
        )
        clean_lang = DEFAULT_LANGUAGE

    rule_translations = MULTILINGUAL_RULE_CATALOG.get(rule_id)
    if not rule_translations:
        raise KeyError(f"Rule ID '{rule_id}' not found in multilingual rule catalog.")

    if clean_lang in rule_translations:
        return rule_translations[clean_lang]

    # Fallback to English
    return rule_translations.get(DEFAULT_LANGUAGE, next(iter(rule_translations.values())))
