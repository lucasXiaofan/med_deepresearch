import csv
import re

def get_case_details(case_id, csv_file='deepsearch_complete.csv'):
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

# Most relevant cases for differential diagnosis of gravid septate uterus
relevant_case_ids = [
    19172,  # Original case - gravid septate uterus with septal placental implantation
    16525,  # Bicornuate uterus with threatened abortion - important differential
    16543,  # Herlyn-Werner-Wunderlich syndrome with didelphys uterus
    10893,  # Uterus didelphys with cervical atresia
    13438,  # Herlyn-Werner-Wunderlich syndrome / OHVIRA syndrome
    18804,  # Unicornuate uterus with ruptured rudimentary horn pregnancy
    12104,  # Congenital vaginal atresia with unicornuate uterus
    18326,  # Accessory and cavitating uterine mass (ACUM)
    16271,  # Bicornuate uterus with bilateral rudimentary horns
    12912   # Infected gartner duct cyst with bicornuate uterus
]

print("Detailed Analysis of Most Relevant Cases for Differential Diagnosis")
print("=" * 100)

for case_id in relevant_case_ids:
    case = get_case_details(case_id)
    if case:
        print(f"\n{'='*80}")
        print(f"CASE ID: {case['case_id']}")
        print(f"FINAL DIAGNOSIS: {case['final_diagnosis']}")
        print(f"{'-'*40}")
        print(f"CLINICAL HISTORY: {case['clinical_history'][:300]}...")
        print(f"\nIMAGING FINDINGS: {case['imaging_findings'][:300]}...")
        if case['differential_diagnosis']:
            print(f"\nDIFFERENTIAL DIAGNOSIS: {case['differential_diagnosis'][:200]}...")
        print(f"\nCATEGORIES: {case['categories']}")
        print(f"{'='*80}")
