import csv
import re

def search_placental_cases(csv_file='deepsearch_complete.csv'):
    results = []
    keywords = ['placenta', 'placental', 'implantation', 'septal']
    
    with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        headers = next(reader)
        
        for row in reader:
            if len(row) >= 11:
                case_title = row[0] if len(row) > 0 else ''
                clinical_history = row[3] if len(row) > 3 else ''
                imaging_findings = row[4] if len(row) > 4 else ''
                discussion = row[5] if len(row) > 5 else ''
                final_diagnosis = row[7] if len(row) > 7 else ''
                
                # Search text
                search_text = f"{clinical_history} {imaging_findings} {discussion} {final_diagnosis}".lower()
                
                # Check for uterine anomaly AND placental terms
                uterine_terms = ['uterus', 'uterine', 'septate', 'bicornuate', 'didelphys', 'unicornuate', 'mullerian']
                placental_terms = ['placenta', 'placental', 'implantation']
                
                has_uterine = any(term in search_text for term in uterine_terms)
                has_placental = any(term in search_text for term in placental_terms)
                
                if has_uterine and has_placental:
                    case_match = re.search(r'case number (\d+)', case_title, re.IGNORECASE)
                    case_id = case_match.group(1) if case_match else 'Unknown'
                    
                    results.append({
                        'case_id': case_id,
                        'case_title': case_title,
                        'clinical_history': clinical_history[:150] + '...' if len(clinical_history) > 150 else clinical_history,
                        'imaging_findings': imaging_findings[:150] + '...' if len(imaging_findings) > 150 else imaging_findings,
                        'final_diagnosis': final_diagnosis
                    })
                    
                    if len(results) >= 15:
                        break
    
    return results

print("Searching for cases with uterine anomalies and placental involvement...")
print("=" * 100)

cases = search_placental_cases()

if cases:
    print(f"\nFound {len(cases)} relevant cases:")
    for i, case in enumerate(cases, 1):
        print(f"\n{i}. Case ID: {case['case_id']}")
        print(f"   Diagnosis: {case['final_diagnosis']}")
        print(f"   Clinical: {case['clinical_history']}")
        print(f"   Imaging: {case['imaging_findings']}")
else:
    print("No cases found.")
