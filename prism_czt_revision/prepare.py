import json
from pathlib import Path
w=Path('prism_czt_revision');p=json.load(open(w/'raw-before.json'))['structuredContent']
req=[]
navy={'red':0,'green':0.16470589,'blue':0.28235295}
cyan={'red':0.24,'green':0.61,'blue':0.72}
slide8=p['slides'][7]['objectId'];slide9=p['slides'][8]['objectId']
def geo(oid,x,y,width,height):
 e=next(e for s in p['slides'] for e in s['pageElements'] if e['objectId']==oid)
 sz=e['size'];req.append({'updatePageElementTransform':{'objectId':oid,'applyMode':'ABSOLUTE','transform':{'scaleX':width*12700/sz['width']['magnitude'],'scaleY':height*12700/sz['height']['magnitude'],'translateX':x,'translateY':y,'unit':'PT'}}})
def text(oid,txt,size=None,bold=None,color=None,bullets=False):
 req.extend([{'deleteText':{'objectId':oid,'textRange':{'type':'ALL'}}},{'insertText':{'objectId':oid,'insertionIndex':0,'text':txt}},{'deleteParagraphBullets':{'objectId':oid,'textRange':{'type':'ALL'}}}])
 style={}
 if size:style['fontSize']={'magnitude':size,'unit':'PT'}
 if bold is not None:style['bold']=bold
 if color:style['foregroundColor']={'opaqueColor':{'rgbColor':color}}
 if style:req.append({'updateTextStyle':{'objectId':oid,'textRange':{'type':'ALL'},'style':style,'fields':','.join(style)}})
 req.append({'updateParagraphStyle':{'objectId':oid,'textRange':{'type':'ALL'},'style':{'indentStart':{'magnitude':0,'unit':'PT'},'indentEnd':{'magnitude':0,'unit':'PT'},'indentFirstLine':{'magnitude':0,'unit':'PT'},'spaceAbove':{'magnitude':0,'unit':'PT'},'spaceBelow':{'magnitude':8 if bullets else 0,'unit':'PT'},'lineSpacing':110},'fields':'indentStart,indentEnd,indentFirstLine,spaceAbove,spaceBelow,lineSpacing'}})
 if bullets:
  req.extend([{'createParagraphBullets':{'objectId':oid,'textRange':{'type':'ALL'},'bulletPreset':'BULLET_DISC_CIRCLE_SQUARE'}},{'updateParagraphStyle':{'objectId':oid,'textRange':{'type':'ALL'},'style':{'indentStart':{'magnitude':12,'unit':'PT'},'indentFirstLine':{'magnitude':0,'unit':'PT'}},'fields':'indentStart,indentFirstLine'}}])
def add(oid,slide,txt,x,y,ww,hh,size,bold=False,color=navy):
 req.append({'createShape':{'objectId':oid,'shapeType':'TEXT_BOX','elementProperties':{'pageObjectId':slide,'size':{'width':{'magnitude':ww,'unit':'PT'},'height':{'magnitude':hh,'unit':'PT'}},'transform':{'scaleX':1,'scaleY':1,'translateX':x,'translateY':y,'unit':'PT'}}}})
 req.append({'insertText':{'objectId':oid,'text':txt,'insertionIndex':0}})
 req.append({'updateTextStyle':{'objectId':oid,'textRange':{'type':'ALL'},'style':{'fontFamily':'Helvetica Neue','fontSize':{'magnitude':size,'unit':'PT'},'bold':bold,'foregroundColor':{'opaqueColor':{'rgbColor':color}}},'fields':'fontFamily,fontSize,bold,foregroundColor'}})
 req.append({'updateParagraphStyle':{'objectId':oid,'textRange':{'type':'ALL'},'style':{'spaceAbove':{'magnitude':0,'unit':'PT'},'spaceBelow':{'magnitude':0,'unit':'PT'},'lineSpacing':105},'fields':'spaceAbove,spaceBelow,lineSpacing'}})
text('h44cae004078c7866_0_32','Why a multichannel CZT detector for PRISM?',25,True)
text('prism_czt_eff','Room-temperature detection of Ag fluorescence at 22.2 keV',16)
geo('hacaab33e851671a_0_3',42,142,260,208)
geo('hacaab33e851671a_0_2',324,153,100,98.9)
for oid in ['hacaab33e851671a_0_0','hacaab33e851671a_0_1']:req.append({'deleteObject':{'objectId':oid}})
geo('prism_czt_design',442,145,236,209)
text('prism_czt_design','2-mm-thick CZT\n20 pixels, 500 µm pitch\nIndependent low-noise channels distribute the rate\nEnergy selection helps reject background',15,False,navy,True)
add('prism_czt_eff_caption_v3',slide8,'Calculated absorption efficiency.\nComparison: 450 µm Si, 1 mm HPGe and 1 mm CZT.',42,346,280,18,9)
add('prism_czt_sensor_caption_v3',slide8,'Illustrative pixelated sensor\nPRISM baseline:\n20-pixel linear array',318,263,115,48,11)
text('h14ac1f20202dfc06_1_17','CZT development and qualification',25,True)
text('prism_psa_context','Prior CZT results at DAΦNE BTF',16,True,cyan)
geo('prism_psa_context',42,110,320,26)
geo('prism_qualification_psa',42,140,315,155.9)
text('prism_psa_context2','Pulse selection preserves fluorescence peaks\nand suppresses coincidence structures.',12,False)
geo('prism_psa_context2',42,300,315,30)
text('prism_ref_357','Manti et al., Condens. Matter 11, 38 (2026).\nPrevious CZT measurements. PRISM targets remain to be validated.',9.5)
geo('prism_ref_357',42,336,319,26)
text('prism_czt_targets','Qualification targets at M15\n\nIntrinsic efficiency >90% at 50 keV\n\nResolution ≤2% at Ag Kα (22.2 keV)\n\nDead time <10%\nPile-up contamination <5%\n\nUnder XAS operating conditions',14.5,False)
geo('prism_czt_targets',380,110,298,184)
req.append({'updateTextStyle':{'objectId':'prism_czt_targets','textRange':{'type':'FIXED_RANGE','startIndex':0,'endIndex':27},'style':{'bold':True,'foregroundColor':{'opaqueColor':{'rgbColor':cyan}}},'fields':'bold,foregroundColor'}})
req.append({'deleteObject':{'objectId':'h4dc4f3af379f64a9_0_56'}})
add('prism_czt_development_v3',slide9,'PRISM development\nPixel calibration and charge-sharing reconstruction\nWaveform DAQ: 64 ch, 16 bit, 125 MS/s',380,301,298,59,12.5)
for i,txt in [(7,'PRISM baseline: monolithic 2-mm-thick CZT crystal, 20-pixel linear array, 500 µm pitch, common cathode and guard ring. The sensor image is illustrative, not the final PRISM layout. The calculated efficiency comparison uses 1-mm CZT, not the 2-mm project baseline. Energy-resolved fluorescence detection helps reject background. Source: FINAL/Progetto.pdf, pp. 4–5. Fabrication and qualification are project activities.'),(8,'The pulse-selection figure shows prior CZT measurements at DAΦNE BTF, as identified by Figure 3 of the submitted proposal and the local 13_CZT/v3_CZT.png caption. It does not demonstrate the future PRISM multichannel detector performance. PRISM will develop dedicated low-noise front-end electronics, waveform acquisition, pixel calibration, gain equalization, charge-sharing reconstruction and pile-up rejection. M15 targets: intrinsic efficiency >90% at 50 keV, energy resolution ≤2% at Ag Kα 22.2 keV, dead time <10% and pile-up contamination <5% under XAS operating conditions. The detector energy resolution selects fluorescence and must be distinguished from the ≤10 eV incident-beam bandwidth. Source: FINAL/Progetto.pdf, ER2, WP2 and MS2.')]:
 oid=p['slides'][i]['slideProperties']['notesPage']['notesProperties']['speakerNotesObjectId']
 req.extend([{'deleteText':{'objectId':oid,'textRange':{'type':'ALL'}}},{'insertText':{'objectId':oid,'text':txt,'insertionIndex':0}}])
json.dump(req,open(w/'requests.json','w'))
(w/'plan.md').write_text('Edit existing slides 8 and 9 in place. Preserve master, title style, logos and footers. Slide 8: explain detector choice; keep efficiency plot and illustrative sensor, delete unrelated drone graphic and off-canvas image. Slide 9: prior CZT evidence plus PRISM development and M15 qualification; keep PSA figure, delete secondary generic pixel illustration. All narrative text remains native and editable. No slide reordering.\n')
print(len(req),'requests prepared')
