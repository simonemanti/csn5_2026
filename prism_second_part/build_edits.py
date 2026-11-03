import json
from pathlib import Path
w=Path(__file__).parent
p=json.load(open(w/'raw-template.json'))['structuredContent']
slides=p['slides']; elements={e['objectId']:e for s in slides for e in s['pageElements']}; req=[]
navy={'red':0,'green':0.16470589,'blue':0.28235295}; teal={'red':0.25490198,'green':0.5882353,'blue':0.7058824};red={'red':0.9019608,'green':0.22352941,'blue':0.27450982}
def tx(e):return ''.join(x.get('textRun',{}).get('content','') for x in e.get('shape',{}).get('text',{}).get('textElements',[]))
def rect(id,x,y,wid,hei):
 e=elements.get(id); sw=e['size']['width']['magnitude'] if e else wid;sh=e['size']['height']['magnitude'] if e else hei
 if e and e['size']['width']['unit']=='EMU':sw/=12700;sh/=12700
 req.append({'updatePageElementTransform':{'objectId':id,'applyMode':'ABSOLUTE','transform':{'scaleX':wid/sw,'scaleY':hei/sh,'translateX':x,'translateY':y,'unit':'PT'}}})
def style(id,size=16,bold=False,color=navy):
 req.append({'updateTextStyle':{'objectId':id,'textRange':{'type':'ALL'},'style':{'fontFamily':'Helvetica Neue','fontSize':{'magnitude':size,'unit':'PT'},'bold':bold,'foregroundColor':{'opaqueColor':{'rgbColor':color}}},'fields':'fontFamily,fontSize,bold,foregroundColor'}})
def replace(id,text,size=None,bold=False):
 old=tx(elements[id]);req.append({'replaceAllText':{'containsText':{'text':old.rstrip('\n'),'matchCase':True},'replaceText':text,'pageObjectIds':[next(s['objectId'] for s in slides if any(e['objectId']==id for e in s['pageElements']))]}})
 if size:style(id,size,bold)
def text(s,id,t,x,y,wid,hei,size=16,bold=False,color=navy):
 req.extend([{'createShape':{'objectId':id,'shapeType':'TEXT_BOX','elementProperties':{'pageObjectId':s,'size':{'width':{'magnitude':wid,'unit':'PT'},'height':{'magnitude':hei,'unit':'PT'}},'transform':{'scaleX':1,'scaleY':1,'translateX':x,'translateY':y,'unit':'PT'}}}},{'insertText':{'objectId':id,'text':t}}]);style(id,size,bold,color)
 req.append({'updateParagraphStyle':{'objectId':id,'textRange':{'type':'ALL'},'style':{'spaceAbove':{'magnitude':0,'unit':'PT'},'spaceBelow':{'magnitude':7,'unit':'PT'},'lineSpacing':110},'fields':'spaceAbove,spaceBelow,lineSpacing'}})
def title(n,t):
 e=slides[n-1]['pageElements'][3]; replace(e['objectId'],t,22 if len(t)>52 else 25,True);rect(e['objectId'],42.5,59,635,38)
def drop(id):req.append({'deleteObject':{'objectId':id}})
def notes(n,t):
 id=slides[n-1]['slideProperties']['notesPage']['notesProperties']['speakerNotesObjectId'];req.append({'insertText':{'objectId':id,'insertionIndex':0,'text':t+'\n'}})
def imgcopy(source,id,s,x,y,wid,hei):
 e=elements[source]; ratio=e['size']['width']['magnitude']/e['size']['height']['magnitude']; ww=min(wid,hei*ratio);hh=ww/ratio
 req.append({'createImage':{'objectId':id,'url':e['image']['contentUrl'],'elementProperties':{'pageObjectId':s,'size':{'width':{'magnitude':ww,'unit':'PT'},'height':{'magnitude':hh,'unit':'PT'}},'transform':{'scaleX':1,'scaleY':1,'translateX':x+(wid-ww)/2,'translateY':y+(hei-hh)/2,'unit':'PT'}}}})
# 8: retain both comparison figures and citation, correct universal fluorescence claim.
s=slides[7]['objectId'];title(8,'Why fluorescence detection for PRISM?')
replace('h1d3d3c759e0906ec_0_49','Transmission requires a suitable,\nhomogeneous sample thickness.\n\nFluorescence extends access to thick,\ndilute or constrained samples.',16)
rect('h1d3d3c759e0906ec_0_49',42,110,330,105)
rect('h1d3d3c759e0906ec_0_48',430,106,220,221)
rect('h1d3d3c759e0906ec_0_50',100,216,148.6,100)
rect('h1d3d3c759e0906ec_0_51',42,344,635,25);style('h1d3d3c759e0906ec_0_51',9)
text(s,'prism_s8_scan','PRISM scans the incident energy and records fluorescence at each step.',42,319,360,34,13,True,teal)
# 11 becomes 9 setup: keep user instrument drawing, fit original aspect ratio.
s=slides[10]['objectId'];title(11,'PRISM setup: selecting and scanning the incident energy')
replace('h1d3d3c759e0906ec_0_59','Ge(880) is the baseline candidate for the Ag K-edge at 25.5 keV.',15)
rect('h1d3d3c759e0906ec_0_59',42,102,635,32)
rect('h44cae004078c7866_0_108',42,138,390,202.24)
text(s,'prism_setup_scan','Crystal rotation and motorized axes preserve the focused spot during the scan.\n\nThe same CZT measures If and I0 in separate motorized configurations.',455,144,220,147,15)
text(s,'prism_setup_sim','SHADOW4 + GEANT4 co-optimize flux, bandwidth, spectral purity and sample response.',455,291,220,68,14,True,teal)
notes(11,'Source: FINAL/Progetto.pdf, methodology pp. 3–7. Ge(880) is a baseline candidate, not a frozen design. I0: sample removed, CZT repositioned into the attenuated direct beam; calibrated attenuation and linear-rate operation. Drawing is conceptual and not to scale. Design freeze M6. Incident bandwidth target ≤10 eV FWHM is distinct from detector energy resolution.')
# 9 becomes 10 evidence.
s=slides[8]['objectId'];title(9,'VOXES provides the experimental starting point')
replace('h1d3d3c759e0906ec_0_55','Existing instrument and infrastructure',16,True);rect('h1d3d3c759e0906ec_0_55',42,105,345,30)
rect('h1d3d3c759e0906ec_0_54',42,142,335,163.2)
rect('h44cae004078c7866_0_109',465,101,135,95.1)
rect('h44cae004078c7866_0_93',420,195,232,145)
text(s,'prism_voxes_bridge','Measured Bragg-angle scan and focusing support PRISM development.\n\nNext: synchronized scans and quantitative fluorescence XAS.',42,293,340,62,14)
rect('h1d3d3c759e0906ec_0_56',42,352,635,17);style('h1d3d3c759e0906ec_0_56',8)
notes(9,'Existing VOXES results shown here were acquired in X-ray emission configurations. They establish controlled crystal rotation and focusing, not demonstrated fluorescence XAS. Commissioning target M18: count rates within 20%, spot size and incident-energy resolution within 10% of simulation predictions. Source: FINAL/Progetto.pdf, pp. 4, 7–8; existing slide references.')
# 10 becomes 11 CZT design. Transfer PSA image to qualification slide.
s=slides[9]['objectId'];title(10,'A custom CZT array for hard-X-ray fluorescence')
rect('h44cae004078c7866_0_107',42,137,265,212)
text(s,'prism_czt_eff','High absorption at room temperature',42,105,275,30,16,True,teal)
text(s,'prism_czt_design','Baseline detector\n2-mm-thick CZT, 20 pixels, 500 µm pitch\n\nIndependent low-noise channels\nDistribute the rate and monitor each pixel\n\nWaveform acquisition\n64 channels, 16 bit, 125 MS/s\n\nCalibration and reconstruction\nGain, charge sharing, pile-up and stability',335,106,340,242,15)
# qualification uses original blank slide 18.
q=slides[17]['objectId'];title(18,'CZT qualification and pulse reconstruction')
imgcopy('h44cae004078c7866_0_92','prism_qualification_psa',q,42,147,355,185)
drop('h44cae004078c7866_0_92')
text(q,'prism_psa_context','Previous pulse-shape-analysis experience',42,108,365,30,16,True,teal)
text(q,'prism_psa_context2','Methods to validate on the PRISM multichannel CZT',42,310,365,35,13)
text(q,'prism_czt_targets','Targets at M15\n\nEfficiency >90% at 50 keV\n\nResolution ≤2% at Ag Kα (22.2 keV)\n\nDead time <10%\nPile-up contamination <5%',425,108,250,219,16)
for id,y in [('h44cae004078c7866_0_91',344),('h44cae004078c7866_0_113',357)]:
 t=tx(elements[id]);text(q,'prism_ref_'+str(y),t,42,y,635,14,8);drop(id)
notes(10,'Design baseline and acquisition specifications: FINAL/Progetto.pdf, pp. 4–5. Efficiency plot is a comparative detector absorption calculation, not a measured qualification result. CZT fabrication and characterization remain project activities.')
notes(18,'The plotted pulse-selection example is prior detector-analysis experience (BEGe/VIP context), not proof that the PRISM CZT already meets its targets. CZT and BEGe references are retained from the original presentation. Qualify efficiency, energy response, gain equalization, linearity, rate dependence, dead time, pile-up and channel uniformity on the multichannel detector. Targets: FINAL/Progetto.pdf, ER2 and MS2. The ≤2% detector resolution at Ag Kα must not be confused with the ≤10 eV incident-beam bandwidth.')
# original impact becomes actual Ag benchmark.
s=slides[13]['objectId'];title(14,'Ag K-edge XANES: the quantitative demonstration')
drop('h1d3d3c759e0906ec_0_60')
replace('h44cae004078c7866_0_112','Reference samples',18,True);rect('h44cae004078c7866_0_112',42,112,300,30)
text(s,'prism_ag_samples','Metallic Ag foil\nEnergy calibration and reproducibility\n\nTwo Ag(I) reference compounds\nDifferent local coordination environments\n\nRealistic sample\nTest discrimination of chemical states',42,149,335,177,16)
text(s,'prism_ag_validation','Acceptance targets',400,112,275,30,18,True,teal)
text(s,'prism_ag_metrics','≤10 eV FWHM\nIncident-beam bandwidth\n\n≥20 edge-step SNR\nAg K-edge XANES\n\nReference-spectrum comparison\nEnergy scale and near-edge features',400,149,275,177,16)
text(s,'prism_ag_norm','Extract Ag Kα, correct background and live time, then normalize to I0.',42,337,635,27,14,True,teal)
notes(14,'Source: FINAL/Progetto.pdf, O3/ER3, methodology and WP4/MS4. Ag K-edge ≈25.5 keV; fluorescence Ag Kα ≈22.2 keV. Compare metallic foil and two Ag(I) compounds with different coordination. These are planned measurements, not existing PRISM spectra. In the thin/dilute limit, corrected If/I0 is proportional to absorption. For thick/concentrated samples assess self-absorption explicitly. Quantify acquisition time and accessible operating domain; do not claim an unvalidated one-hour performance. Reference dataset M21, realistic-sample demonstration M24.')
# organization retain Gantt and add actual result gates.
s=slides[11]['objectId'];title(12,'From instrument design to the Ag demonstration')
rect('h44cae004078c7866_0_97',42,112,420,262.5)
text(s,'prism_timeline','M6  Design frozen\nValidated simulations and specifications\n\nM15  CZT qualified\nCalibration and performance dataset\n\nM18  Instrument commissioned\nMeasured vs simulated performance\n\nM24  Ag demonstration\nReference and realistic-sample datasets',480,110,195,250,14)
notes(12,'Timeline and milestones: FINAL/Progetto.pdf pp. 7–8. WP1 M1–6, WP2 M4–15, WP3 M10–18, WP4 M16–24. Reference-compound dataset D3 M21, realistic-sample dataset D4 M24. Original Gantt retained. The oral narrative follows scientific concepts; the timeline summarizes delivery.')
# synergies into team and support.
s=slides[12]['objectId'];title(13,'Team responsibilities and supporting collaborations')
replace('h44cae004078c7866_0_111','Simone Manti — 1.0 FTE\nProject lead, simulations and measurements\n\nAlessandro Scordo — 0.3 FTE\nCrystal optics, ray tracing and integration\n\nMassimiliano Bazzi — 0.3 FTE\nElectronics and DAQ\n\nCatalina Curceanu — 0.1 FTE\nScientific supervision and validation',14)
rect('h44cae004078c7866_0_111',42,108,350,242)
text(s,'prism_synergies','Palermo and ENRICH COST\nCZT development and simulation expertise\n\nVOXES, KAONNIS and VIP\nInfrastructure and detector experience\n\nDue2Lab, Rigaku, Quantum Design\nLetters of support\n\nEuAPS and AQUA\nFuture transfer after laboratory validation',410,108,265,242,14)
notes(13,'Team and FTE verified in FINAL/Progetto.pdf p.7, collaborations pp.9–10. Total 1.7 FTE. Industrial letters of support indicate interest, not guaranteed delivery or co-funding. Transfer to EuAPS follows laboratory validation.')
# Budget preserves original itemized table.
s=slides[14]['objectId'];title(15,'Resources for the integrated instrument')
rect('h44cae004078c7866_0_98',42,136,425,212.5)
text(s,'prism_budget_total','112 k€ requested',490,112,190,38,23,True,teal)
text(s,'prism_budget_years','2027: 69 k€\n2028: 43 k€\n\n45 k€ estimated in kind\nExisting VOXES equipment and infrastructure',490,161,190,157,16)
notes(15,'Source: FINAL/Progetto.pdf, Costs, and FINAL/Costs.pdf. Requested total €112k: €69k in 2027 and €43k in 2028. Estimated in-kind €45k is separate. The original itemized cost table is retained.')
# Risks: existing screenshot is costs, replace with relevant readable native text.
s=slides[15]['objectId'];title(16,'Main risks and practical mitigation')
drop('h44cae004078c7866_0_100');drop('h44cae004078c7866_0_101')
text(s,'prism_risk_names','Simulation accuracy\n\n\nCZT optimization takes longer\n\n\nCritical-component delays\n\n\nFluorescence rate or SNR below target',42,111,265,235,16,True)
text(s,'prism_risk_mitigations','Benchmark against analytical calculations and VOXES measurements.\n\nUse the existing Si PIN for preliminary reference measurements while CZT work continues.\n\nStart alignment and integration with compatible VOXES components.\n\nOptimize acceptance, scan steps and dwell times while preserving bandwidth and background rejection.',330,111,345,242,15)
notes(16,'Mitigations from FINAL/Progetto.pdf, Risk Assessment. The existing Si PIN is a reduced-efficiency commissioning fallback, not an equivalent replacement for the final CZT demonstration. No numerical risk-priority score is claimed.')
# conclusion combines impact.
s=slides[16]['objectId'];title(17,'PRISM: a validated laboratory fluorescence-XAS platform')
text(s,'prism_conclusion_optics','Crystal optics and synchronized scanning',42,116,635,30,20,True,teal)
text(s,'prism_conclusion_optics_body','A commissioned instrument supported by source-to-detector simulations.',42,151,635,32,17)
text(s,'prism_conclusion_czt','Room-temperature multichannel CZT detection',42,203,635,30,20,True,teal)
text(s,'prism_conclusion_czt_body','A calibrated detector, waveform readout and validated reconstruction methods.',42,238,635,32,17)
text(s,'prism_conclusion_ag','Ag K-edge XANES as the validation benchmark',42,290,635,30,20,True,teal)
text(s,'prism_conclusion_ag_body','Quantitative reference data and a defined operating domain for realistic samples.',42,325,635,32,17)
notes(17,'Expected outputs and impact, not achieved results: FINAL/Progetto.pdf, objectives, deliverables and impact sections. Emphasize reusable detector/readout, validated simulations and analysis procedures. Laboratory validation establishes the basis for long measurement campaigns and future transfer.')
order=[*range(7),7,10,8,9,17,13,11,12,14,15,16,18,19,20]
json.dump({'requests':req},open(w/'edits.json','w'),ensure_ascii=False)
json.dump([slides[i]['objectId'] for i in order],open(w/'order.json','w'))
(w/'content-plan.md').write_text('Existing native deck edited in place after a Drive backup. First seven slides preserved. Source: FINAL/Progetto.pdf and FINAL/Costs.pdf, matching the current deck; older local v2 context is superseded for this task by the final proposal.\n\n'+ '\n'.join(f'{j+1}: reuse original slide {i+1}' for j,i in enumerate(order))+'\n\nMedia: preserve transmission figures, setup drawing, VOXES evidence, efficiency calculation, Gantt and costs. Move the prior PSA example to qualification. Delete the Sigray image from the former impact placeholder and the erroneous cost-table image from Risks. Add no synthetic scientific plots.\n')
print(len(req),'requests')
