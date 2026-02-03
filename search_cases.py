import csv
import re

def search_cases(keyword, csv_file='deepsearch_complete.csv', max_results=20):
    results = []
    with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        headers = next(reader)
        
        for row in reader:
            if len(row) >= 11:  # Ensure we have all columns
                case_title = row[0] if len(row) > 0 else ''
                clinical_history = row[3] if len(row) > 3 else ''
                imaging_findings = row[4] if len(row) > 4 else ''
                discussion = row[5] if len(row) > 5 else ''
                final_diagnosis = row[7] if len(row) > 7 else ''
                
                # Search in multiple fields
                search_text = f"{case_title} {clinical_history} {imaging_findings} {discussion} {final_diagnosis}".lower()
                keyword_lower = keyword.lower()
                
                if keyword_lower in search_text:
                    # Extract case number
                    case_match = re.search(r'case number (\d+)', case_title, re.IGNORECASE)
                    case_id = case_match.group(1) if case_match else 'Unknown'
                    
                    results.append({
                        'case_id': case_id,
                        'case_title': case_title,
                        'clinical_history': clinical_history[:200] + '...' if len(clinical_history) > 200 else clinical_history,
                        'imaging_findings': imaging_findings[:200] + '...' if len(imaging_findings) > 200 else imaging_findings,
                        'final_diagnosis': final_diagnosis[:100] + '...' if len(final_diagnosis) > 100 else final_diagnosis
                    })
                    
                    if len(results) >= max_results:
                        break
    
    return results

# Search for uterine anomaly cases
keywords = [
    'septate uterus',
    'bicornuate uterus',
    'didelphys uterus',
    'uterine septum',
    'gravid uterus',
    'mullerian anomaly',
    'uterine malformation'
]

print("Searching for diagnosis-relevant cases...")
print("=" * 80)

for keyword in keywords:
    print(f"\nSearching for: '{keyword}'")
    print("-" * 40)
    
    cases = search_cases(keyword, max_results=5)
    
    if cases:
        for i, case in enumerate(cases, 1):
            print(f"\n{i}. Case ID: {case['case_id']}")
            print(f"   Title: {case['case_title']}")
            print(f"   Clinical: {case['clinical_history']}")
            print(f"   Imaging: {case['imaging_findings']}")
            print(f"   Diagnosis: {case['final_diagnosis']}")
    else:
        print("No cases found.")
    
    print()
