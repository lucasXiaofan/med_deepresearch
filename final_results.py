import csv
import re

def get_full_case(case_id, csv_file='deepsearch_complete.csv'):
    with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        headers = next(reader)
        
        for row in reader:
            if len(row) >= 11:
                case_title = row[0] if len(row) > 0 else ''
                case_match = re.search(r'case number (\d+)', case_title, re.IGNORECASE)
                if case_match and case_match.group(1) == str(case_id):
                    return {
                        'case_id': case_id,
                        'case_title': case_title,
                        'clinical_history': row[3] if len(row) > 3 else '',
                        'imaging_findings': row[4] if len(row) > 4 else '',
                        'discussion': row[5] if len(row) > 5 else '',
                        'differential_diagnosis': row[6] if len(row) > 6 else '',
                        'final_diagnosis': row[7] if len(row) > 7 else '',
                        'categories': row[10] if len(row) > 10 else ''
                    }
    return None

# Most relevant cases for differential diagnosis
selected_cases = [
    19172, 16525, 16543, 10893, 13438, 
    18804, 18326, 16271, 11882, 12660
]

print("FINAL RESULTS: Diagnosis-Relevant Cases for Clinical Case 19172")
print("=" * 90)

for i, case_id in enumerate(selected_cases, 1):
    case = get_full_case(case_id)
    if case:
        print(f"\n{i}. CASE ID: {case['case_id']}")
        print(f"   DIAGNOSIS: {case['final_diagnosis']}")
        
        # Diagnostic relevance
        if case_id == 19172:
            print("   RELEVANCE: ORIGINAL CASE - Key features: thin septum, fetus straddles septum, placental implantation on septum")
        elif case_id == 16525:
            print("   RELEVANCE: KEY DIFFERENTIAL - Bicornuate uterus appearance, distinguishes from septate uterus")
        elif case_id == 16543:
            print("   REVANCE: COMPLEX ANOMALY - Herlyn-Werner-Wunderlich syndrome with renal agenesis")
        elif case_id == 10893:
            print("   RELEVANCE: COMPLETE DUPLICATION - Uterus didelphys vs partial septation")
        elif case_id == 13438:
            print("   RELEVANCE: ASSOCIATED ANOMALIES - OHVIRA syndrome with vaginal septum")
        elif case_id == 18804:
            print("   RELEVANCE: CRITICAL COMPLICATION - Unicornuate uterus with ruptured horn")
        elif case_id == 18326:
            print("   RELEVANCE: MIMICKING CONDITION - Accessory cavitated uterine mass")
        elif case_id == 16271:
            print("   RELEVANCE: SPECTRUM - Bicornuate with rudimentary horns")
        elif case_id == 11882:
            print("   RELEVANCE: PLACENTAL ISSUES - Placenta previa percreta")
        elif case_id == 12660:
            print("   RELEVANCE: COMPLICATION - Uterine rupture risk")

print("\n" + "=" * 90)
print("DIAGNOSTIC VALUE SUMMARY:")
print("These 10 cases provide comprehensive coverage for:")
print("1. Distinguishing septate vs bicornuate vs didelphys uteri")
print("2. Recognizing associated congenital anomalies")
print("3. Identifying pregnancy complications in uterine anomalies")
print("4. Understanding placental implantation patterns")
print("5. Differential diagnosis of Mullerian duct anomalies")
