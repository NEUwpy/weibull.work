"""Legacy authority compatibility capsule for A-E1 formal r5.

A versioned, immutable, run-scoped capsule that lets the production historical
verifier (``verify_historical_authority``) reconstruct the 3 scoped code files
whose sealed SHA-256 was computed over bytes with MIXED line endings (a mix of
CRLF and lone LF). Git stores LF-normalized blobs, so neither the LF form (git
blob as-is) nor the CRLF form (LF->CRLF deterministic reconstruction) can match
the sealed hash for these 3 files at d2a056f.

The capsule is GENERATED ONCE (at the time the r5 manifest was sealed) from the
working-tree bytes (which match the sealed hash) and the d2a056f Git LF blob.
For each file it records the byte offsets in the LF blob where a CR should be
inserted before the LF to reconstruct the original mixed-newline bytes.

At verification time the production historical verifier:

  (a) reads the LF blob from the git object database at the sealed code_commit;
  (b) applies the capsule mask to reconstruct the original bytes;
  (c) verifies that removing CRs from the reconstructed bytes yields exactly
      the LF blob (anti-tamper on the mask itself);
  (d) verifies that sha256(reconstructed) == sealed hash (content integrity).

Binding (Codex R4 REVISE final). The capsule is uniquely scoped to:
  - run_id             = A-E1-formal-r5-20260727-222417
  - manifest_version   = study02-formal-v1
  - code_commit        = d2a056fdfe650af9f2992f8ea85f8b2daab2fbb3
  - authority_sha256   = 3f8f86aa0e40fdc6ab40a6f037aa0b2752eb9e25ddb7e67489b480013a4f3faa
  - scoped_code_sha256 = d91999088ad3f950a4e9b077904f209256ae43d541a9ccc23fb42fc64ed05624
  - 3 scoped paths with their sealed SHA-256 + d2a056f LF-blob SHA-256.

Any binding mismatch (wrong run_id, wrong commit, wrong authority, wrong scoped
SHA, missing/extra file, path change, mask tamper, hash tamper) fails closed.
The capsule is never used for any other run, commit, manifest version, or file
set; other runs use the existing LF/CRLF path unchanged.

The capsule NEVER reads the working tree at verification time. It uses only:
  - git object database content (content-addressed by the sealed code_commit);
  - the embedded mask data (a constant in this module).

This satisfies R4-5's no-working-tree-fallback rule while letting the historical
verifier accept the r5 sealed predecessor as a terminal sealed run.

Constraints (Codex R4 REVISE final):
  - A-E1 r5 is NOT modified or re-sealed.
  - The working-tree fallback is NOT restored.
  - No general mixed-newline rule is introduced.
  - The capsule is versioned, immutable, and uniquely scoped to r5.
  - Other runs, commits, v2 manifests, and future formal runs are unaffected.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence


_CAPSULE_SCHEMA_VERSION = "study02-legacy-authority-capsule-v1"
_CAPSULE_TOP_FIELDS = frozenset({
    "schema_version", "run_id", "manifest_version", "code_commit",
    "scoped_code_sha256", "authority_sha256", "files",
})
_CAPSULE_FILE_FIELDS = frozenset({
    "scoped_path", "repo_path", "sealed_sha256", "git_lf_sha256",
    "lf_to_crlf_positions",
})


# The immutable capsule payload. Mask positions are byte offsets in the
# d2a056f LF blob where a CR must be inserted before the LF to reconstruct
# the original mixed-newline bytes. They were computed once by walking the
# sealed mixed-newline bytes and the LF blob in lockstep; the reconstructed
# bytes' SHA-256 matches the sealed hash for each file.
_LEGACY_AUTHORITY_CAPSULE_DATA: dict[str, Any] = {
    "schema_version": _CAPSULE_SCHEMA_VERSION,
    "run_id": "A-E1-formal-r5-20260727-222417",
    "manifest_version": "study02-formal-v1",
    "code_commit": "d2a056fdfe650af9f2992f8ea85f8b2daab2fbb3",
    "scoped_code_sha256": "d91999088ad3f950a4e9b077904f209256ae43d541a9ccc23fb42fc64ed05624",
    "authority_sha256": "3f8f86aa0e40fdc6ab40a6f037aa0b2752eb9e25ddb7e67489b480013a4f3faa",
    "files": (
        {
            "scoped_path": "studies/mdm_delta/generate_curve_study_data.py",
            "repo_path": "python/studies/mdm_delta/generate_curve_study_data.py",
            "sealed_sha256": "7d19313941bf356768803859e10227b78d389d58f910f5aedfc6759cd5352cc9",
            "git_lf_sha256": "df4a61c640f983d01b7a33adefa6bf555e90dff339f9e4c9533e3fe84fe35810",
            # 250 LF-blob byte offsets where the LF should be expanded to CRLF
            # to reconstruct the original mixed-newline bytes.
            "lf_to_crlf_positions": (
        3, 57, 58, 134, 182, 183, 190, 222, 262, 266, 267, 443,
        471, 472, 473, 529, 567, 596, 651, 673, 674, 675, 1755, 1756,
        2199, 2200, 3467, 3500, 3535, 3751, 3752, 3753, 3815, 3875, 3891, 3920,
        3948, 3949, 3963, 4042, 4102, 4123, 4170, 4197, 4224, 4225, 4239, 4306,
        4388, 4448, 4469, 4516, 4543, 4570, 4571, 4585, 4650, 4728, 4788, 4809,
        4856, 4883, 4910, 4911, 4952, 4953, 4954, 5026, 5042, 5064, 5092, 5150,
        5210, 5231, 5278, 5305, 5332, 5373, 5374, 5375, 5387, 5469, 5519, 5520,
        5572, 5586, 5715, 5844, 5978, 6107, 6237, 6506, 6512, 6513, 6557, 6580,
        6581, 6604, 6634, 6674, 6782, 6847, 6848, 6869, 6955, 6956, 6976, 7040,
        7109, 7110, 7530, 7561, 7578, 7674, 7764, 7811, 7858, 7859, 7907, 7956,
        7957, 7989, 8068, 8151, 8209, 8210, 8301, 8411, 8462, 8463, 8487, 8533,
        8560, 8606, 8636, 8671, 8689, 8728, 8742, 8775, 8803, 8832, 8833, 8856,
        8904, 8952, 8953, 8984, 9012, 9046, 9080, 9112, 9148, 9176, 9210, 9249,
        9282, 9341, 9396, 9440, 9468, 9509, 9552, 9753, 9794, 9840, 9863, 9912,
        9961, 10010, 10061, 10110, 10116, 10117, 10142, 10202, 10270, 10311, 10312, 10389,
        10468, 10542, 10543, 10639, 10640, 10673, 10701, 10801, 10932, 10943, 10944, 10998,
        11043, 11069, 11123, 11212, 11260, 11317, 11351, 11377, 11425, 11472, 11483, 11484,
        11518, 11531, 11785, 11847, 11878, 11911, 11952, 11967, 11978, 12018, 12062, 12108,
        12133, 12163, 12299, 12464, 12627, 12761, 12776, 13410, 13453, 13481, 13559, 13651,
        13742, 13761, 13806, 13846, 13880, 13927, 13942, 14129, 14444, 14445, 14488, 14544,
        14601, 14602, 14641, 14699, 14767, 14832, 14833, 14834, 14861, 14872,
            ),
        },
        {
            "scoped_path": "studies/mle/simulate.py",
            "repo_path": "python/studies/mle/simulate.py",
            "sealed_sha256": "9658798525c9131947f71522335b7fc1d1f8eabefa1d73041e84d9c209178ba9",
            "git_lf_sha256": "dd19f2d1668d8dce811245087833fdace6d1aae6bdf22d7cf58c7739a8723656",
            # 633 LF-blob byte offsets where the LF should be expanded to CRLF
            # to reconstruct the original mixed-newline bytes.
            "lf_to_crlf_positions": (
        619, 620, 636, 662, 663, 727, 756, 757, 794, 831, 832, 866,
        911, 912, 949, 986, 987, 1006, 1044, 1045, 1079, 1116, 1117, 1151,
        1214, 1260, 1329, 1330, 1346, 1358, 1408, 1458, 1476, 1550, 1594, 1595,
        1616, 1636, 1640, 1641, 1652, 1662, 1674, 1685, 1701, 1720, 1745, 1775,
        1827, 1828, 1861, 1919, 1968, 1969, 1981, 2009, 2010, 2011, 2057, 2076,
        2093, 2109, 2132, 2150, 2152, 2153, 2189, 2213, 2238, 2261, 2288, 2321,
        2323, 2324, 2325, 2369, 2424, 2480, 2507, 2508, 2582, 2616, 2656, 2684,
        2720, 2770, 2796, 2797, 2862, 2863, 2864, 2907, 2945, 2985, 2986, 3011,
        3055, 3085, 3132, 3159, 3194, 3228, 3262, 3316, 3326, 3370, 3371, 3372,
        3450, 3482, 3497, 3548, 3606, 3629, 3664, 3695, 3741, 3780, 3827, 3841,
        3900, 3951, 3969, 4015, 4051, 4052, 4053, 4154, 4201, 4226, 4261, 4319,
        4346, 4347, 4348, 4392, 4400, 4422, 4498, 4506, 4515, 4551, 4590, 4591,
        4637, 4661, 4662, 4684, 4711, 4751, 4771, 4772, 4773, 4815, 4844, 4887,
        4915, 4974, 5006, 5019, 5041, 5070, 5092, 5114, 5133, 5167, 5195, 5226,
        5237, 5262, 5268, 5269, 5270, 5317, 5346, 5418, 5461, 5516, 5574, 5575,
        5576, 5633, 5697, 5768, 5769, 5770, 5811, 5835, 5854, 5890, 5898, 5949,
        5950, 6010, 6018, 6049, 6074, 6095, 6164, 6202, 6203, 6231, 6249, 6250,
        6272, 6273, 6325, 6356, 6379, 6417, 6444, 6489, 6512, 6550, 6585, 6622,
        6644, 6682, 6765, 6809, 6870, 6939, 6999, 7000, 7049, 7109, 7168, 7210,
        7250, 7290, 7291, 7318, 7349, 7376, 7418, 7458, 7499, 7541, 7582, 7608,
        7695, 7760, 7833, 7897, 7898, 7929, 7946, 7975, 8019, 8061, 8089, 8115,
        8176, 8177, 8208, 8209, 8210, 8232, 8250, 8278, 8312, 8336, 8356, 8374,
        8397, 8423, 8434, 8478, 8509, 8549, 8592, 8632, 8633, 8661, 8731, 8799,
        8873, 8961, 8962, 8984, 8985, 9053, 9084, 9085, 9108, 9192, 9283, 9315,
        9316, 9361, 9388, 9414, 9451, 9494, 9537, 9581, 9603, 9647, 9648, 9675,
        9772, 9773, 9798, 9846, 9847, 9874, 9915, 9916, 9947, 9982, 10060, 10078,
        10172, 10221, 10267, 10319, 10348, 10387, 10425, 10465, 10505, 10544, 10585, 10617,
        10636, 10637, 10670, 10671, 10684, 10723, 10749, 10755, 10756, 10757, 10831, 10887,
        10925, 10971, 11013, 11014, 11033, 11078, 11079, 11117, 11194, 11195, 11224, 11268,
        11283, 11284, 11317, 11398, 11488, 11489, 11536, 11537, 11556, 11606, 11641, 11683,
        11684, 11715, 11739, 11772, 11818, 11864, 11890, 11896, 11897, 11928, 11947, 11986,
        12058, 12068, 12115, 12140, 12192, 12259, 12305, 12344, 12401, 12496, 12497, 12521,
        12575, 12590, 12591, 12610, 12628, 12651, 12652, 12672, 12731, 12751, 12752, 12795,
        12858, 12902, 12903, 12928, 13010, 13079, 13080, 13115, 13180, 13227, 13237, 13238,
        13287, 13288, 13311, 13334, 13364, 13442, 13473, 13525, 13595, 13605, 13606, 13639,
        13691, 13733, 13785, 13811, 13825, 13872, 13916, 13917, 13940, 13941, 13960, 14014,
        14072, 14165, 14166, 14200, 14201, 14221, 14251, 14298, 14342, 14403, 14448, 14504,
        14524, 14525, 14526, 14597, 14656, 14691, 14692, 14720, 14767, 14782, 14783, 14807,
        14845, 14872, 14893, 14932, 15012, 15013, 15093, 15180, 15181, 15223, 15224, 15298,
        15299, 15373, 15410, 15442, 15443, 15519, 15576, 15612, 15684, 15732, 15781, 15820,
        15865, 15866, 15885, 15954, 15988, 15989, 16015, 16061, 16062, 16081, 16137, 16180,
        16181, 16211, 16249, 16291, 16292, 16293, 16365, 16415, 16450, 16451, 16471, 16529,
        16549, 16550, 16569, 16598, 16671, 16753, 16839, 16920, 16921, 16940, 16975, 17005,
        17072, 17133, 17195, 17196, 17215, 17245, 17275, 17329, 17373, 17404, 17466, 17512,
        17561, 17571, 17601, 17602, 17622, 17623, 17624, 17695, 17748, 17766, 17767, 17795,
        17846, 17880, 17881, 17903, 17943, 17970, 18020, 18047, 18048, 18074, 18075, 18076,
        18141, 18171, 18206, 18207, 18223, 18270, 18317, 18371, 18418, 18419, 18442, 18466,
        18539, 18576, 18621, 18632, 18633, 18656, 18676, 18751, 18872, 18923, 18934, 18935,
        18958, 18982, 19066, 19119, 19179, 19289, 19300, 19301, 19321, 19339, 19387, 19444,
        19454, 19460, 19461, 19508, 19565, 19625, 19626, 19627, 19639, 19748, 19814, 19899,
        19988, 20079, 20180, 20270, 20362, 20363, 20394, 20395, 20420, 20512, 20548, 20587,
        20588, 20621, 20685, 20705, 20706, 20725, 20769, 20770, 20789, 20808, 20864, 20886,
        20943, 20964, 21020, 21030, 21089, 21090, 21091, 21118, 21129,
            ),
        },
        {
            "scoped_path": "studies/wmle/simulate.py",
            "repo_path": "python/studies/wmle/simulate.py",
            "sealed_sha256": "24d7ecca22f52fe37b9f684b887fb41fb6e4e43ac4f7eaf178cad1c549dd811a",
            "git_lf_sha256": "5b9ad6f1b2a6f922350cfaa4aa7f22bd7a80c5cf65f37a5c59a6691df4d421ce",
            # 633 LF-blob byte offsets where the LF should be expanded to CRLF
            # to reconstruct the original mixed-newline bytes.
            "lf_to_crlf_positions": (
        620, 621, 637, 664, 665, 729, 758, 759, 796, 833, 834, 868,
        913, 914, 951, 988, 989, 1008, 1046, 1047, 1081, 1118, 1119, 1153,
        1217, 1263, 1332, 1333, 1349, 1361, 1411, 1461, 1479, 1553, 1597, 1598,
        1619, 1639, 1643, 1644, 1655, 1665, 1677, 1688, 1704, 1723, 1748, 1778,
        1830, 1831, 1864, 1922, 1971, 1972, 1984, 2014, 2015, 2016, 2062, 2081,
        2098, 2114, 2137, 2155, 2157, 2158, 2194, 2218, 2243, 2266, 2293, 2326,
        2328, 2329, 2330, 2374, 2429, 2485, 2512, 2513, 2587, 2621, 2661, 2689,
        2725, 2775, 2801, 2802, 2867, 2868, 2869, 2912, 2950, 2990, 2991, 3016,
        3060, 3090, 3137, 3164, 3199, 3233, 3267, 3321, 3331, 3375, 3376, 3377,
        3455, 3487, 3502, 3553, 3611, 3634, 3669, 3700, 3746, 3785, 3832, 3846,
        3905, 3956, 3974, 4020, 4056, 4057, 4058, 4159, 4206, 4231, 4266, 4324,
        4351, 4352, 4353, 4398, 4406, 4429, 4505, 4513, 4522, 4559, 4598, 4599,
        4645, 4669, 4670, 4692, 4719, 4760, 4780, 4781, 4782, 4824, 4853, 4896,
        4924, 4983, 5015, 5028, 5050, 5079, 5101, 5123, 5142, 5176, 5204, 5235,
        5246, 5271, 5277, 5278, 5279, 5326, 5355, 5427, 5470, 5525, 5583, 5584,
        5585, 5642, 5706, 5777, 5778, 5779, 5820, 5844, 5863, 5899, 5907, 5958,
        5959, 6019, 6027, 6058, 6083, 6104, 6173, 6211, 6212, 6240, 6258, 6259,
        6281, 6282, 6334, 6365, 6388, 6426, 6453, 6498, 6521, 6559, 6594, 6631,
        6653, 6691, 6774, 6818, 6879, 6948, 7008, 7009, 7058, 7118, 7177, 7219,
        7259, 7299, 7300, 7327, 7358, 7385, 7427, 7467, 7508, 7550, 7591, 7617,
        7704, 7769, 7842, 7906, 7907, 7938, 7955, 7984, 8028, 8070, 8098, 8124,
        8185, 8186, 8217, 8218, 8219, 8241, 8259, 8287, 8321, 8345, 8365, 8383,
        8406, 8432, 8443, 8487, 8518, 8558, 8601, 8641, 8642, 8670, 8740, 8808,
        8882, 8970, 8971, 8993, 8994, 9062, 9093, 9094, 9117, 9201, 9292, 9324,
        9325, 9370, 9397, 9423, 9460, 9503, 9546, 9590, 9612, 9656, 9657, 9684,
        9781, 9782, 9808, 9857, 9858, 9885, 9926, 9927, 9958, 9993, 10071, 10089,
        10183, 10232, 10278, 10330, 10359, 10398, 10436, 10476, 10516, 10555, 10596, 10628,
        10647, 10648, 10681, 10682, 10695, 10734, 10760, 10766, 10767, 10768, 10842, 10898,
        10936, 10982, 11024, 11025, 11044, 11089, 11090, 11128, 11205, 11206, 11235, 11279,
        11294, 11295, 11328, 11409, 11499, 11500, 11547, 11548, 11567, 11603, 11638, 11680,
        11681, 11712, 11736, 11769, 11815, 11861, 11887, 11893, 11894, 11925, 11944, 11983,
        12055, 12065, 12112, 12137, 12189, 12256, 12302, 12341, 12398, 12493, 12494, 12518,
        12572, 12587, 12588, 12607, 12625, 12648, 12649, 12669, 12728, 12748, 12749, 12792,
        12855, 12899, 12900, 12925, 13007, 13076, 13077, 13112, 13177, 13224, 13234, 13235,
        13284, 13285, 13308, 13331, 13361, 13439, 13470, 13522, 13592, 13602, 13603, 13636,
        13688, 13730, 13782, 13808, 13822, 13869, 13913, 13914, 13937, 13938, 13957, 14011,
        14069, 14162, 14163, 14197, 14198, 14218, 14248, 14295, 14339, 14400, 14445, 14501,
        14521, 14522, 14523, 14594, 14653, 14688, 14689, 14717, 14764, 14779, 14780, 14804,
        14842, 14869, 14890, 14929, 15009, 15010, 15090, 15177, 15178, 15220, 15221, 15295,
        15296, 15370, 15407, 15439, 15440, 15516, 15573, 15609, 15681, 15729, 15778, 15817,
        15862, 15863, 15882, 15951, 15985, 15986, 16012, 16058, 16059, 16078, 16134, 16177,
        16178, 16208, 16246, 16288, 16289, 16290, 16362, 16412, 16447, 16448, 16468, 16526,
        16546, 16547, 16566, 16595, 16668, 16750, 16836, 16917, 16918, 16937, 16972, 17002,
        17069, 17130, 17192, 17193, 17212, 17242, 17272, 17326, 17370, 17401, 17463, 17509,
        17558, 17568, 17598, 17599, 17619, 17620, 17621, 17692, 17745, 17763, 17764, 17792,
        17843, 17877, 17878, 17900, 17940, 17967, 18017, 18044, 18045, 18071, 18072, 18073,
        18138, 18168, 18203, 18204, 18220, 18267, 18314, 18368, 18416, 18417, 18440, 18464,
        18537, 18574, 18619, 18630, 18631, 18654, 18674, 18749, 18870, 18921, 18932, 18933,
        18956, 18980, 19064, 19117, 19177, 19287, 19298, 19299, 19319, 19337, 19385, 19442,
        19452, 19458, 19459, 19506, 19563, 19623, 19624, 19625, 19637, 19747, 19813, 19898,
        19987, 20078, 20179, 20269, 20361, 20362, 20393, 20394, 20419, 20512, 20548, 20587,
        20588, 20621, 20685, 20705, 20706, 20725, 20769, 20770, 20789, 20808, 20864, 20886,
        20943, 20964, 21020, 21030, 21089, 21090, 21091, 21118, 21129,
            ),
        }
    ),
}


def _validate_mask_canonical(lf_blob: bytes, positions: Sequence[int]) -> None:
    """Reject non-canonical masks before application.

    A canonical mask is: a tuple of non-bool non-negative ints, strictly
    ascending (no duplicates, no reordering), each within ``[0, len(lf_blob))``,
    and each pointing at an LF byte (``0x0a``). Duplicates, out-of-range
    positions, reorders, and non-LF positions are all fail-closed — the
    final reconstructed SHA check alone is NOT sufficient because some
    modifications are silently equivalent under ``set(positions)``.
    """
    if not isinstance(positions, tuple):
        raise ValueError("mask positions must be a tuple")
    prev = -1
    for pos in positions:
        if isinstance(pos, bool) or not isinstance(pos, int):
            raise ValueError("mask position must be a non-bool int")
        if pos < 0:
            raise ValueError("mask position must be non-negative")
        if pos >= len(lf_blob):
            raise ValueError(f"mask position {pos} is out of range (blob length {len(lf_blob)})")
        if pos <= prev:
            raise ValueError(f"mask positions must be strictly ascending; {pos} <= {prev}")
        if lf_blob[pos] != 0x0a:
            raise ValueError(f"mask position {pos} does not point to an LF byte (got 0x{lf_blob[pos]:02x})")
        prev = pos


def _apply_lf_to_crlf_mask(lf_blob: bytes, positions: Sequence[int]) -> bytes:
    """Reconstruct mixed-newline bytes from an LF blob and a position mask.

    For every byte offset in ``positions`` where ``lf_blob[offset] == 0x0a``,
    the LF is expanded to CRLF in the output. Every other byte is passed
    through unchanged. This is the deterministic inverse of git CRLF->LF
    normalization for files whose original line endings were a mix of CRLF
    and lone LF (and is a no-op on CR-only or pure-LF blobs, which have no
    mixed-newline ambiguity to begin with).

    The mask is validated canonical (strictly ascending, no duplicates,
    in-range, at-LF) before application — non-canonical masks fail closed.
    """
    _validate_mask_canonical(lf_blob, positions)
    out = bytearray()
    pos_set = set(positions)
    for index, byte in enumerate(lf_blob):
        if byte == 0x0a and index in pos_set:
            out.append(0x0d)
            out.append(0x0a)
        else:
            out.append(byte)
    return bytes(out)


def _validate_capsule_shape(capsule: Mapping[str, Any]) -> None:
    """Fail closed if the capsule's schema or file-entry shape is wrong.

    Pure structural validation; the binding fields and mask are verified at
    use time by ``reconstruct_capsule_file_bytes`` (any tampering surfaces
    there as a SHA-256 mismatch).
    """
    if set(capsule) != _CAPSULE_TOP_FIELDS:
        raise ValueError("legacy authority capsule top-level schema mismatch")
    if capsule["schema_version"] != _CAPSULE_SCHEMA_VERSION:
        raise ValueError("legacy authority capsule schema_version is unsupported")
    files = capsule["files"]
    if not isinstance(files, tuple) or len(files) != 3:
        raise ValueError("legacy authority capsule must bind exactly 3 files")
    seen_paths: set[str] = set()
    for entry in files:
        if set(entry) != _CAPSULE_FILE_FIELDS:
            raise ValueError("legacy authority capsule file entry schema mismatch")
        scoped_path = entry["scoped_path"]
        if not isinstance(scoped_path, str) or scoped_path in seen_paths:
            raise ValueError("legacy authority capsule has a missing or duplicate path")
        seen_paths.add(scoped_path)
        if not isinstance(entry["lf_to_crlf_positions"], tuple):
            raise ValueError("legacy authority capsule mask must be a tuple")
        for value in entry["lf_to_crlf_positions"]:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError("legacy authority capsule mask position must be a non-negative int")


def get_legacy_authority_capsule() -> dict[str, Any]:
    """Return the validated legacy authority capsule (immutable, r5-only).

    Returns a deep copy so callers cannot mutate the module-level canonical
    capsule (nested dicts/tuples are not shared).
    """
    import copy
    capsule = copy.deepcopy(_LEGACY_AUTHORITY_CAPSULE_DATA)
    _validate_capsule_shape(capsule)
    return capsule


def capsule_binding_matches(
    capsule: Mapping[str, Any], *,
    run_id: str, manifest_version: str, code_commit: str,
    authority_sha256: str, scoped_code_sha256: str,
) -> bool:
    """True iff the capsule's run-binding fields exactly match the inputs.

    The capsule is uniquely scoped to one sealed run; ANY field mismatch means
    the capsule does not apply (the verifier then uses the existing LF/CRLF
    path for every scoped file, which fails closed for r5 3 mixed files but
    is the correct behavior for any other run).
    """
    return (
        capsule["run_id"] == run_id
        and capsule["manifest_version"] == manifest_version
        and str(capsule["code_commit"]).lower() == str(code_commit).lower()
        and capsule["authority_sha256"] == authority_sha256
        and capsule["scoped_code_sha256"] == scoped_code_sha256
    )


def _read_git_lf_blob(repo_root: Path, code_commit: str, repo_path: str) -> bytes:
    """Read a single blob from the git object database (no checkout/worktree)."""
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", "cat-file", "-p", f"{code_commit}:{repo_path}"],
        cwd=str(repo_root), capture_output=True,
    )
    if result.returncode != 0:
        stderr_text = result.stderr.decode("utf-8", "replace").strip()
        raise ValueError(
            f"legacy authority capsule: git cat-file failed for {repo_path!r} "
            f"at {code_commit}: {stderr_text}"
        )
    return result.stdout


def reconstruct_capsule_file_bytes(
    capsule: Mapping[str, Any], repo_root: Path, scoped_path: str,
) -> bytes:
    """Reconstruct + verify the original mixed-newline bytes for one capsule file.

    Reads the LF blob from the git object database at ``capsule["code_commit"]``
    and applies the capsule mask. Three fail-closed checks follow:

      (a) sha256(git LF blob) == capsule["git_lf_sha256"]
          (proves the right blob was read -- anti-tamper on the git object);
      (b) reconstructed.replace(CRLF, LF) == LF blob
          (proves the mask only expands LFs to CRLFs -- anti-tamper on the mask);
      (c) sha256(reconstructed) == capsule["sealed_sha256"]
          (proves the reconstructed content matches the sealed hash).

    The working tree is NEVER read. Returns the reconstructed bytes on success.
    """
    _validate_capsule_shape(capsule)
    entry = next((f for f in capsule["files"] if f["scoped_path"] == scoped_path), None)
    if entry is None:
        raise ValueError(f"legacy authority capsule has no entry for {scoped_path!r}")
    lf_blob = _read_git_lf_blob(repo_root, capsule["code_commit"], entry["repo_path"])
    lf_sha = hashlib.sha256(lf_blob).hexdigest()
    if lf_sha != entry["git_lf_sha256"]:
        raise ValueError(
            f"legacy authority capsule: git LF blob hash mismatch for {scoped_path!r}: "
            f"expected {entry['git_lf_sha256'][:16]}, got {lf_sha[:16]}"
        )
    reconstructed = _apply_lf_to_crlf_mask(lf_blob, entry["lf_to_crlf_positions"])
    if reconstructed.replace(b"\r\n", b"\n") != lf_blob:
        raise ValueError(
            f"legacy authority capsule: mask tamper detected for {scoped_path!r} "
            "(removing CRs from the reconstructed bytes does not recover the LF blob)"
        )
    recon_sha = hashlib.sha256(reconstructed).hexdigest()
    if recon_sha != entry["sealed_sha256"]:
        raise ValueError(
            f"legacy authority capsule: reconstructed hash mismatch for {scoped_path!r}: "
            f"expected {entry['sealed_sha256'][:16]}, got {recon_sha[:16]}"
        )
    return reconstructed


def capsule_files_for_verify(
    capsule: Mapping[str, Any], repo_root: Path, sealed_files: Mapping[str, str],
) -> dict[str, str]:
    """Reconstruct + verify every capsule file, returning ``{scoped_path: sha256}``.

    Fail-closed checks against ``sealed_files`` (the manifest sealed scoped
    code dict):

      - every capsule path must be present in ``sealed_files`` (no extra path);
      - every capsule path sealed SHA in ``sealed_files`` must equal the
        capsule's ``sealed_sha256`` for that path (no hash drift);
      - the capsule must bind at least one file (no empty capsule).

    Each file bytes are then reconstructed + verified via
    ``reconstruct_capsule_file_bytes``. The returned dict is the matched
    per-file hash map for the capsule paths ONLY; the caller is responsible
    for the non-capsule files and the aggregate ``scoped_code_sha256`` check.
    """
    _validate_capsule_shape(capsule)
    capsule_paths = {f["scoped_path"] for f in capsule["files"]}
    extra = capsule_paths - set(sealed_files)
    if extra:
        raise ValueError(
            f"legacy authority capsule binds paths absent from sealed scoped_code_files: "
            f"{sorted(extra)}"
        )
    matched: dict[str, str] = {}
    for entry in capsule["files"]:
        scoped_path = entry["scoped_path"]
        sealed_hash = sealed_files[scoped_path]
        if sealed_hash != entry["sealed_sha256"]:
            raise ValueError(
                f"legacy authority capsule sealed_sha256 mismatch for {scoped_path!r}: "
                f"sealed_files={sealed_hash[:16]}, capsule={entry['sealed_sha256'][:16]}"
            )
        reconstructed = reconstruct_capsule_file_bytes(capsule, repo_root, scoped_path)
        matched[scoped_path] = hashlib.sha256(reconstructed).hexdigest()
    return matched


__all__ = [
    "get_legacy_authority_capsule",
    "capsule_binding_matches",
    "reconstruct_capsule_file_bytes",
    "capsule_files_for_verify",
    "_apply_lf_to_crlf_mask",
]
