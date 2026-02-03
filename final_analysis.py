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

# Select the most relevant cases for differential diagnosis
selected_cases = [
    19172,  # Original case - Gravid septate uterus with septal placental implantation
    16525,  # Bicornuate uterus with threatened abortion - Key differential
    16543,  # Herlyn-Werner-Wunderlich syndrome - Complex anomaly
    10893,  # Uterus didelphys with cervical atresia - Complete duplication
    13438,  # OHVIRA syndrome - Associated renal anomalies
    18804,  # Unicornuate uterus with ruptured horn - Important complication
    18326,  # Accessory cavitated uterine mass - Mimics uterine anomalies
    16271,  # Bicornuate with rudimentary horns - Spectrum of anomalies
    11882,  # Placenta previa percreta - Placental implantation issues
    12660   # Uterine rupture - Important complication to consider
]

print("FINAL ANALYSIS: Most Relevant Cases for Differential Diagnosis")
print("=" * 100)
print("\nOriginal Case (19172): Gravid septate uterus with septal placental implantation")
print("Key features: Thin central septum, fetus straddles septum, placental implantation on septum")
print("Differential: Bicornuate vs didelphys vs septate uterus")
print("-" * 80)

for i, case_id in enumerate(selected_cases, 1):
    case = get_full_case(case_id)
    if case:
        print(f"\n{i}. CASE ID: {case['case_id']}")
        print(f"   DIAGNOSIS: {case['final_diagnosis']}")
        
        # Diagnostic relevance explanation
        relevance = ""
        if case_id == 19172:
            relevance = "ORIGINAL CASE - Demonstrates key features of septate uterus with fetus straddling septum and septal placental implantation"
        elif case_id == 16525:
            relevance = "KEY DIFFERENTIAL - Shows bicornuate uterus appearance, important to distinguish from septate uterus"
        elif case_id == 16543:
            relevance = "COMPLEX ANOMALY - Demonstrates Herlyn-Werner-Wunderlich syndrome with didelphys uterus and renal agenesis"
        elif case_id == 10893:
            relevance = "COMPLETE DUPLICATION - Uterus didelphys case, shows complete uterine duplication vs partial septation"
        elif case_id == 13438:
            relevance = "ASSOCIATED ANOMALIES - OHVIRA syndrome shows uterine duplication with vaginal septum and renal anomalies"
        elif case_id == 18804:
            relevance = "IMPORTANT COMPLICATION - Unicornuate uterus with ruptured horn pregnancy, shows risks of asymmetric anomalies"
        elif case_id == 18326:
            relevance = "MIMICKING CONDITION - Accessory cavitated uterine mass can mimic uterine anomalies"
        elif case_id == 16271:
            relevance = "SPECTRUM OF ANOMALIES - Bicornuate uterus with rudimentary horns shows range of Mullerian anomalies"
        elif case_id == 11882:
            relevance = "PLACENTAL COMPLICATIONS - Placenta previa percreta shows abnormal placental implantation patterns"
        elif case_id == 12660:
            relevance = "CRITICAL COMPLICATION - Uterine rupture case, important complication of uterine anomalies in pregnancy"
        
        print(f"   RELEVANCE: {relevance}")
        
        # Key imaging features
        imaging = case['imaging_findings'][:200].replace('\n', ' ')
        print(f"   KEY IMAGING: {imaging}...")
        
        if case['differential_diagnosis']:
            diff = case['differential_diagnosis'][:150].replace('\n', ' ')
            print(f"   DIFFERENTIALS: {diff}...")

print("\n" + "=" * 100)
print("SUMMARY OF DIAGNOSTIC VALUE:")
print("1. Cases 19172, 16525, 10893 provide direct comparisons between septate, bicornuate, and didelphys uteri")
print("2. Cases 16543, 13438 demonstrate associated anomalies (renal agenesis, vaginal septa)")
print("3. Cases 18804, 12660 show critical complications (rupture, hemorrhage)")
print("4. Case 18326 shows a condition that can mimic uterine anomalies")
print("5. Cases 16271, 11882 show spectrum of anomalies and placental issues")
print("\nThese cases collectively provide comprehensive coverage of:")
print("- Key imaging differences between Mullerian anomalies")
- Associated congenital abnormalities
- Pregnancy complications specific to uterine anomalies
- Differential diagnosis considerations")
