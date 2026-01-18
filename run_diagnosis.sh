#!/bin/bash

# Run the med_research_agent to make a final diagnosis

cd /Users/xiaofanlu/Documents/github_repos/med_deepresearch

PYTHONPATH=src/agent uv run python src/agent/single_agent.py --agent med_research_agent "$(cat <<'EOF'
You are tasked with making a final diagnosis for the following medical case. Search the medical case database for similar cases to help inform your diagnosis.

## Clinical History
A 27-year-old nulliparous female came for her first antenatal scan at 32 weeks of gestation with no prior early antenatal scans. She presented with a bilobed abdominal contour seen externally as two distinct bulges with a central vertical depression. No earlier imaging had been done.

## Imaging Findings
An ultrasound examination revealed a thin central septum partially dividing the uterus into two hemicavities. The amniotic sac was seen occupying both the uterine hemicavities. The foetus was viable, with the foetal abdomen and lower extremities seen in the right hemicavity, and the foetal head and upper extremities extending into the left hemicavity across the central septum (Figures 1 and 2). Nearly two-thirds of the placenta was implanted on the left side of the central septum, with the rest of it implanted on the anterior wall of the left hemicavity (Figure 3). No vascularity was detected in the uterine septum on Doppler ultrasound.

## Images
- Image 1: USG image showing a thin central uterine septum dividing the amniotic sac within two uterine hemicavities, with few loops of umbilical cord and part of a foetal lower limb seen within the right hemicavity, placenta implanted on the left side of the septum and another loop of the umbilical cord within amniotic fluid within the left hemicavity.
- Image 2: USG image showing a thin central uterine septum dividing the amniotic sac within two hemicavities, with part of the foetal abdomen seen within the right hemicavity, placenta implanted on the left side of the septum and a few loops of the umbilical cord within amniotic fluid within the left hemicavity.
- Image 3: USG image showing the left uterine hemicavity with anterior placenta and one of the foetal upper limbs.

## Discussion
A uterine septum is a congenital Müllerian anomaly where a fibrous or fibromuscular band divides the endometrial cavity partially or completely. It results from incomplete resorption of the medial walls of the fused Müllerian ducts. The septum is typically avascular and poorly distensible, which can impair implantation and placental development in pregnancy.

In a septate uterus, pregnancy typically occurs in one hemicavity, as the septum restricts expansion into both sides. In rare cases, pregnancy can continue despite placental implantation on the septum. Diagnostic pearls include a narrowed uterine contour with persistent midline echo and extension of the gestational sac across the septum. No vascularity was detected in the uterine septum on Doppler ultrasound.

## Question
Based on the clinical history, imaging findings, and discussion above, what is the most likely diagnosis?

**Options**:
A. Gravid bicornuate uterus with intercornual communication
B. Gravid didelphys uterus with partial fusion
C. Gravid septate uterus with septal placental implantation
D. Gravid arcuate uterus with exaggerated indentation
E. Gravid uterus with intrauterine synechiae or band

Search the medical database for similar cases involving uterine anomalies, septate uterus, or Müllerian anomalies in pregnancy. Then provide your final diagnosis with reasoning.
EOF
)"
