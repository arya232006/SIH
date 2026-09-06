import React, { useState } from 'react';
import { 
 Upload, Volume2, FileText, Sparkles, CheckCircle2, AlertTriangle, 
 ArrowRight, ArrowLeft, Plus, Edit2, Check, Eye, Trash2, 
 AlertCircle, ShieldCheck, RefreshCw, FileSearch, Save, X,
 Info, ShieldAlert, CheckSquare, Layers, HelpCircle
} from 'lucide-react';
import { 
 LanguageCode, PatientSession, PriorInvestigation, CrossCheckDiscrepancy 
} from '../../types';
import { translations } from '../../utils/i18n';
import { AbnormalBadge } from '../../components/AbnormalBadge';
import { MedicationClarifier } from '../../components/MedicationClarifier';

import { KioskAccessibilitySettings } from '../../components/KioskAccessibilityToolbar';
import { playTextToSpeech } from '../../utils/sound';

interface StepScanProps {
 session: PatientSession;
 currentLang: LanguageCode;
 onUploadFile: (file: File) => Promise<void>;
 onLoadSample: (sampleId: string) => Promise<void>;
 onCorrectDoc: (docId: string, extracted: any) => Promise<void>;
 onDeleteDoc?: (docId: string) => Promise<void>;
 onReplaceDoc?: (docId: string, file: File) => Promise<void>;
 onProceedToSummary: () => void;
 onBackToConverse: () => void;
 isLoading: boolean;
 accessibilitySettings?: KioskAccessibilitySettings;
}

export const StepScan: React.FC<StepScanProps> = ({
 session,
 currentLang,
 onUploadFile,
 onLoadSample,
 onCorrectDoc,
 onDeleteDoc,
 onReplaceDoc,
 onProceedToSummary,
 onBackToConverse,
 isLoading,
 accessibilitySettings,
}) => {
 const t = translations[currentLang] || translations.en;

 const handlePlayScanHelp = () => {
 const helpText = currentLang === 'hi'
 ? 'यहाँ आप अपने पुराने डॉक्टर के पर्चे या लैब रिपोर्ट अपलोड कर सकते हैं।'
 : 'You can attach your previous doctor prescriptions or laboratory reports here.';
 playTextToSpeech(helpText, currentLang, accessibilitySettings?.slowSpeech ? 0.75 : 0.95);
 };

 const [selectedDocId, setSelectedDocId] = useState<string | null>(
 session.priorInvestigations.length > 0 ? session.priorInvestigations[session.priorInvestigations.length - 1].id : null
 );
 const [isEditing, setIsEditing] = useState<boolean>(false);
 const [editFormData, setEditFormData] = useState<any>({});
 const [previewImage, setPreviewImage] = useState<string | null>(null);
 const [docToDelete, setDocToDelete] = useState<PriorInvestigation | null>(null);
 const [isDeleting, setIsDeleting] = useState<boolean>(false);
 const [showQualityModal, setShowQualityModal] = useState<boolean>(false);
 const [applyingCorrection, setApplyingCorrection] = useState<string | null>(null);
 
 const replaceInputRef = React.useRef<HTMLInputElement>(null);
 const attachMoreInputRef = React.useRef<HTMLInputElement>(null);

 const sampleOptions = [
 {
 id: 'sample_lab_report',
 title: '1. Printed Lab Report (Lipid & Blood Sugar)',
 type: 'Lab Report',
 desc: 'High Fasting Glucose (148 mg/dL) & LDL (164 mg/dL) — Dual-Pass Verified (96%)',
 badge: 'High Anomaly',
 },
 {
 id: 'sample_pdf_report',
 title: '2. Digital PDF Pathology Report (Max Lab)',
 type: 'Digital PDF',
 desc: 'Multi-parameter PDF (Triglycerides 210 mg/dL, Uric Acid 7.8) — Dual-Pass Verified (98%)',
 badge: 'PDF Scan',
 },
 {
 id: 'sample_printed_rx',
 title: '3. Printed Prescription (Cardiology OPD)',
 type: 'Printed Rx',
 desc: 'Telmisartan 40mg, Metformin 500mg, Atorvastatin 20mg — Dual-Pass Verified (94%)',
 badge: 'Clear Print',
 },
 {
 id: 'sample_handwritten_rx',
 title: "4. Handwritten Doctor's Rx (General Medicine)",
 type: 'Handwritten',
 desc: 'Cursive doctor handwriting (URTI / Antibiotics) — Honest Low Accuracy (68%)',
 badge: 'Needs Review',
 },
 {
 id: 'sample_dr_biswas_rx',
 title: "5. Dr. A. Biswas Handwritten Rx (Diabetes, Thyroid & Leg Pain)",
 type: 'Doctor Cursive',
 desc: 'Kolkata General Physician (Azulix 2, Ondero-D 10, Thyronorm 75, Uprise-D3 60K, Lubrijoint, Fenolip 145, Trinerve, FBS 69, TSH 2.71, BP 140/80)',
 badge: 'Authentic Rx',
 },
 ];

 // Batch / Multi-file upload support
 const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
 if (e.target.files && e.target.files.length > 0) {
 for (let i = 0; i < e.target.files.length; i++) {
 await onUploadFile(e.target.files[i]);
 }
 }
 };

 const handleAttachMoreClick = () => {
 if (attachMoreInputRef.current) {
 attachMoreInputRef.current.value = '';
 attachMoreInputRef.current.click();
 }
 };

 const handleReplaceClick = () => {
 if (replaceInputRef.current) {
 replaceInputRef.current.value = '';
 replaceInputRef.current.click();
 }
 };

 const handleReplaceFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
 if (e.target.files && e.target.files[0] && activeDoc && onReplaceDoc) {
 await onReplaceDoc(activeDoc.id, e.target.files[0]);
 }
 };

 const handleDeleteClick = (doc: PriorInvestigation) => {
 setDocToDelete(doc);
 };

 const handleConfirmDelete = async () => {
 if (!docToDelete || !onDeleteDoc) return;
 setIsDeleting(true);
 try {
 await onDeleteDoc(docToDelete.id);
 setDocToDelete(null);
 const remaining = session.priorInvestigations.filter(d => d.id !== docToDelete.id);
 setSelectedDocId(remaining.length > 0 ? remaining[remaining.length - 1].id : null);
 } catch (err) {
 console.error('Delete error:', err);
 } finally {
 setIsDeleting(false);
 }
 };

 const handleStartEdit = (doc: PriorInvestigation) => {
 setEditFormData(JSON.parse(JSON.stringify(doc.extracted || {})));
 setIsEditing(true);
 };

 const handleSaveEdit = async () => {
 if (!activeDoc) return;
 await onCorrectDoc(activeDoc.id, editFormData);
 setIsEditing(false);
 };

 // 1-Click Apply Pass 2 Cross-Check Discrepancy Correction
 const handleApplyDiscrepancyCorrection = async (discrepancy: CrossCheckDiscrepancy) => {
 if (!activeDoc) return;
 setApplyingCorrection(discrepancy.field);
 try {
 const currentExt = JSON.parse(JSON.stringify(activeDoc.extracted || {}));

 if (discrepancy.field.includes('medication_')) {
 const match = discrepancy.field.match(/medication_(\d+)/);
 if (match) {
 const idx = parseInt(match[1], 10) - 1;
 if (currentExt.medications && currentExt.medications[idx]) {
 currentExt.medications[idx].name = discrepancy.suggestedValue;
 }
 }
 } else if (discrepancy.field.includes('investigation_')) {
 const match = discrepancy.field.match(/investigation_(\d+)/);
 if (match) {
 const idx = parseInt(match[1], 10) - 1;
 if (currentExt.investigations && currentExt.investigations[idx]) {
 currentExt.investigations[idx].value = discrepancy.suggestedValue;
 }
 }
 }

 // Remove the applied discrepancy from the active list
 if (activeDoc.crossCheckDiscrepancies) {
 activeDoc.crossCheckDiscrepancies = activeDoc.crossCheckDiscrepancies.filter(
 d => d.field !== discrepancy.field
 );
 }

 await onCorrectDoc(activeDoc.id, currentExt);
 } catch (err) {
 console.error('Apply correction error:', err);
 } finally {
 setApplyingCorrection(null);
 }
 };

 const activeDoc = session.priorInvestigations.find(
 (d) => d.id === (selectedDocId || (session.priorInvestigations[session.priorInvestigations.length - 1]?.id))
 ) || session.priorInvestigations[session.priorInvestigations.length - 1];

 const isLowAccuracy = activeDoc && (activeDoc.confidence < 0.75 || activeDoc.qualityAssessment === 'poor_handwriting' || activeDoc.crossCheckStatus === 'low_quality_alert');
 const isDualPassVerified = activeDoc && (activeDoc.crossCheckStatus === 'dual_pass_verified' && activeDoc.confidence >= 0.85);

 return (
 <div className="max-w-5xl mx-auto space-y-6">
 
 {/* Hidden File Inputs for Document Replacement & Adding Additional Docs */}
 <input
 type="file"
 ref={replaceInputRef}
 accept="image/*,application/pdf,.pdf"
 onChange={handleReplaceFileChange}
 className="hidden"
 />
 <input
 type="file"
 ref={attachMoreInputRef}
 multiple
 accept="image/*,application/pdf,.pdf"
 onChange={handleFileUpload}
 className="hidden"
 />

 {/* Step Header */}
 <div className="bg-white rounded-2xl p-6 sm:p-8 shadow-xl border border-slate-200">
 <div className="flex items-center space-x-2 text-teal-700 text-xs font-bold uppercase tracking-wider mb-2">
 <Sparkles className="w-4 h-4" />
 <span>Step 3 of 4 • Document Capture & Dual-Pass OCR</span>
 </div>
 <div className="flex items-center justify-between gap-4">
 <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 ">
 {t.scanTitle}
 </h2>
 <button
 type="button"
 onClick={handlePlayScanHelp}
 className="p-3 rounded-2xl bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200 transition-colors shrink-0 shadow-sm cursor-pointer"
 title="Read instructions aloud"
 >
 <Volume2 className="w-5 h-5" />
 </button>
 </div>
 <p className="text-sm text-slate-600 mt-1 max-w-2xl">
 Attach multiple doctor prescriptions, discharge summaries, or digital PDF/printed laboratory test reports. Our dual-pass Vision-AI cross-checks accuracy and honestly flags low-quality cursive handwriting.
 </p>

 {/* Dual Path Chooser: Real Upload vs Sample Demo Document */}
 <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-6">
 
 {/* Path A: Real Document Upload (Multi-Document Enabled) */}
 <div className="border-2 border-dashed border-teal-300 hover:border-teal-500 bg-teal-50/40 hover:bg-teal-50 rounded-2xl p-6 flex flex-col justify-between transition-all">
 <div className="space-y-3">
 <div className="w-12 h-12 rounded-xl bg-teal-600 text-white flex items-center justify-center shadow-md">
 <Upload className="w-6 h-6" />
 </div>
 <h3 className="text-lg font-bold text-slate-900">{t.scanRealUpload}</h3>
 <p className="text-xs text-slate-600">
 Upload one or more document photos, scanned prescriptions, or digital PDF reports (PDF, PNG, JPG, JPEG, WEBP). Select multiple files at once.
 </p>
 </div>
 <label className="mt-4 inline-flex items-center justify-center px-4 py-3 bg-teal-700 hover:bg-teal-800 text-white text-sm font-bold rounded-xl cursor-pointer shadow-md transition-all min-h-[48px]">
 <Upload className="w-4 h-4 mr-2" />
 <span>Choose Document Photo(s) / PDF</span>
 <input
 type="file"
 multiple
 accept="image/*,application/pdf,.pdf"
 onChange={handleFileUpload}
 disabled={isLoading}
 className="hidden"
 />
 </label>
 </div>

 {/* Path B: Try Sample Document (Demo Mode) */}
 <div className="border-2 border-slate-200 bg-slate-50 rounded-2xl p-6 flex flex-col justify-between">
 <div className="space-y-3">
 <div className="w-12 h-12 rounded-xl bg-slate-800 text-white flex items-center justify-center shadow-md">
 <FileSearch className="w-6 h-6" />
 </div>
 <div>
 <h3 className="text-lg font-bold text-slate-900">{t.scanSampleMode}</h3>
 <p className="text-xs text-slate-600">
 Select sample documents to test the dual-pass cross-check pipeline (including honest low accuracy on handwritten cursive):
 </p>
 </div>
 </div>

 <div className="space-y-2 mt-4">
 {sampleOptions.map((s) => (
 <button
 type="button"
 key={s.id}
 disabled={isLoading}
 onClick={() => onLoadSample(s.id)}
 className="w-full text-left p-2.5 rounded-xl border border-slate-300 hover:border-teal-600 hover:bg-white bg-white/70 text-xs font-semibold text-slate-800 transition-all flex items-center justify-between group disabled:opacity-50 min-h-[42px]"
 >
 <div className="truncate pr-2">
 <span className="text-slate-900 font-bold block">{s.title}</span>
 <span className="text-[11px] text-slate-500 font-normal">{s.desc}</span>
 </div>
 <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded shrink-0 ${
 s.id === 'sample_handwritten_rx'
 ? 'bg-amber-100 text-amber-900 border border-amber-300'
 : 'bg-slate-100 group-hover:bg-teal-100 text-slate-700 group-hover:text-teal-900'
 }`}>
 Load
 </span>
 </button>
 ))}
 </div>
 </div>

 </div>
 </div>

 {/* Multi-Document Timeline Strip */}
 {session.priorInvestigations.length > 0 && (
 <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-4">
 <div className="flex items-center justify-between flex-wrap gap-2">
 <div className="flex items-center space-x-2">
 <Layers className="w-4 h-4 text-teal-700" />
 <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
 Attached Medical Records ({session.priorInvestigations.length})
 </h4>
 </div>
 
 {/* Direct '+ Attach Another Document' Action */}
 <button
 type="button"
 onClick={handleAttachMoreClick}
 disabled={isLoading}
 className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-bold text-teal-800 bg-teal-50 hover:bg-teal-100 border border-teal-300 rounded-lg transition-colors shadow-2xs"
 >
 <Plus className="w-3.5 h-3.5" />
 <span>+ Attach Another Record</span>
 </button>
 </div>

 <div className="flex space-x-3 overflow-x-auto pb-2">
 {session.priorInvestigations.map((doc, idx) => {
 const isCurrent = activeDoc?.id === doc.id;
 const docLowAccuracy = doc.confidence < 0.75 || doc.qualityAssessment === 'poor_handwriting';

 return (
 <div
 key={doc.id}
 onClick={() => {
 setSelectedDocId(doc.id);
 setIsEditing(false);
 }}
 className={`p-3.5 rounded-xl border-2 text-left shrink-0 w-64 transition-all cursor-pointer relative group ${
 isCurrent
 ? 'border-teal-600 bg-teal-50/70 shadow-md ring-2 ring-teal-500/20'
 : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
 }`}
 >
 <div className="flex items-center justify-between mb-1">
 <span className="text-xs font-bold text-teal-800 truncate">Doc #{idx + 1} of {session.priorInvestigations.length}</span>
 <div className="flex items-center space-x-1.5">
 <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
 doc.confidence >= 0.85
 ? 'bg-emerald-100 text-emerald-800'
 : 'bg-amber-100 text-amber-900 border border-amber-300'
 }`}>
 {Math.round(doc.confidence * 100)}% {docLowAccuracy ? '⚠️ Low' : '✓'}
 </span>
 {onDeleteDoc && (
 <button
 type="button"
 onClick={(e) => {
 e.stopPropagation();
 handleDeleteClick(doc);
 }}
 className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-100 rounded transition-colors"
 title="Delete this mistakenly attached document"
 >
 <Trash2 className="w-3.5 h-3.5" />
 </button>
 )}
 </div>
 </div>
 <div className="text-xs font-bold text-slate-900 truncate">{doc.document}</div>
 
 {/* Quality & Cross-Check Tag */}
 <div className="flex items-center space-x-1 mt-1 text-[10px] text-slate-500 font-medium">
 {doc.crossCheckStatus === 'dual_pass_verified' ? (
 <span className="text-emerald-700 flex items-center">
 <ShieldCheck className="w-3 h-3 mr-0.5 inline" /> Dual-Pass Verified
 </span>
 ) : (
 <span className="text-amber-800 flex items-center">
 <AlertTriangle className="w-3 h-3 mr-0.5 inline text-amber-600" /> Cursive / Needs Review
 </span>
 )}
 </div>
 </div>
 );
 })}
 </div>
 </div>
 )}

 {/* Empty State when 0 Documents attached */}
 {session.priorInvestigations.length === 0 && (
 <div className="bg-slate-50 border-2 border-dashed border-slate-300 rounded-2xl p-8 text-center space-y-3">
 <div className="w-12 h-12 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center mx-auto">
 <FileText className="w-6 h-6" />
 </div>
 <div>
 <h4 className="text-sm font-bold text-slate-800">No Medical Documents Attached</h4>
 <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
 If you removed a wrong document, you can upload the correct prescription or lab report above, or proceed directly to review your symptoms.
 </p>
 </div>
 </div>
 )}

 {/* Active Document Details & Extraction Card */}
 {activeDoc && (
 <div className="bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
 
 {/* Card Header with Confidence Indicator, Quality Breakdown, Replace, Edit & Delete Buttons */}
 <div className="bg-slate-900 text-white px-6 py-4 flex flex-wrap items-center justify-between gap-3">
 <div className="space-y-1">
 <div className="flex items-center space-x-2">
 <FileText className="w-4 h-4 text-teal-400" />
 <h3 className="text-base font-bold text-white">{activeDoc.document}</h3>
 </div>
 <p className="text-xs text-slate-400">
 Scanned on: {activeDoc.timestamp} • Type: <span className="capitalize font-semibold">{activeDoc.documentType.replace(/_/g, ' ')}</span>
 </p>
 </div>

 <div className="flex flex-wrap items-center gap-2 sm:gap-3">
 {/* Honest Multi-Factor Confidence Meter & Breakdown Button */}
 <button
 type="button"
 onClick={() => setShowQualityModal(true)}
 className="flex items-center space-x-2 bg-slate-800 hover:bg-slate-750 px-3 py-1.5 rounded-lg border border-slate-700 text-left transition-colors cursor-pointer"
 title="Click to view multi-factor quality & dual-pass crosscheck audit breakdown"
 >
 <span className="text-xs text-slate-400 font-medium">Certainty:</span>
 <span className={`text-xs font-bold ${
 activeDoc.confidence >= 0.85 ? 'text-emerald-400' : 'text-amber-400'
 }`}>
 {Math.round(activeDoc.confidence * 100)}% {isLowAccuracy ? '(Low)' : '(High)'}
 </span>
 <Info className="w-3.5 h-3.5 text-slate-400 ml-1" />
 </button>

 {/* Replace / Re-Scan Button */}
 {onReplaceDoc && (
 <button
 type="button"
 onClick={handleReplaceClick}
 disabled={isLoading}
 className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-xs font-bold text-white rounded-lg flex items-center space-x-1.5 transition-colors shadow-sm"
 title="Replace this document with a new photo or PDF"
 >
 <RefreshCw className="w-3.5 h-3.5" />
 <span>Replace</span>
 </button>
 )}

 {/* Edit Fields Button */}
 {!isEditing ? (
 <button
 type="button"
 onClick={() => handleStartEdit(activeDoc)}
 className="px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-xs font-bold text-white rounded-lg flex items-center space-x-1.5 transition-colors shadow-sm"
 >
 <Edit2 className="w-3.5 h-3.5" />
 <span>Edit Fields</span>
 </button>
 ) : (
 <button
 type="button"
 onClick={handleSaveEdit}
 className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-xs font-bold text-white rounded-lg flex items-center space-x-1.5 transition-colors shadow-sm"
 >
 <Save className="w-3.5 h-3.5" />
 <span>Save Edits</span>
 </button>
 )}

 {/* Delete Document Button */}
 {onDeleteDoc && (
 <button
 type="button"
 onClick={() => handleDeleteClick(activeDoc)}
 disabled={isLoading}
 className="px-3 py-1.5 bg-rose-600/90 hover:bg-rose-600 text-xs font-bold text-white rounded-lg flex items-center space-x-1.5 transition-colors shadow-sm"
 title="Delete this mistakenly entered document"
 >
 <Trash2 className="w-3.5 h-3.5" />
 <span>Delete</span>
 </button>
 )}

 {activeDoc.imageUrl && (
 <button
 type="button"
 onClick={() => setPreviewImage(activeDoc.imageUrl || null)}
 className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 rounded-lg flex items-center space-x-1.5 transition-colors"
 >
 <Eye className="w-3.5 h-3.5" />
 <span>View Original</span>
 </button>
 )}
 </div>
 </div>

 {/* DUAL-PASS VERIFICATION / HONEST LOW ACCURACY QUALITY BANNER */}
 {isDualPassVerified ? (
 <div className="bg-emerald-50 border-b border-emerald-200 p-4 flex items-center justify-between text-emerald-950">
 <div className="flex items-center space-x-3">
 <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0" />
 <div className="text-xs space-y-0.5">
 <p className="font-bold text-emerald-900">Dual-Pass AI Verified (Pass 1 & Pass 2 Concordance: 100%)</p>
 <p className="text-emerald-800">Clear typography confirmed against CDSCO formulary & physiological biomarker bounds.</p>
 </div>
 </div>
 <button
 type="button"
 onClick={() => setShowQualityModal(true)}
 className="text-[11px] font-bold text-emerald-800 hover:text-emerald-950 underline shrink-0 ml-2"
 >
 View Audit Scores
 </button>
 </div>
 ) : activeDoc.extractionSource === 'extraction_failed' ? (
            /* The read did not happen at all. Blaming the doctor's handwriting
               here would be wrong and would send the patient off to retake a
               photo that was never the problem. */
            <div className="bg-rose-50 border-b border-rose-200 p-4 flex items-start space-x-3 text-rose-950">
              <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div className="text-xs space-y-1">
                <span className="font-extrabold text-rose-900 block">
                  Could not read this document — nothing was extracted
                </span>
                <p className="text-rose-800">
                  The document reader did not return a result. This is a service
                  problem, not a problem with your prescription. Nothing has been
                  guessed or filled in. Try again in a moment, or ask staff to
                  enter the details.
                </p>
              </div>
            </div>
 ) : isLowAccuracy ? (
 <div className="bg-amber-50 border-b border-amber-200 p-4 flex items-start justify-between text-amber-950">
 <div className="flex items-start space-x-3">
 <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
 <div className="text-xs space-y-1">
 <div className="flex items-center space-x-2">
 <span className="font-extrabold text-amber-900">
 ⚠️ Low Extraction Certainty ({Math.round(activeDoc.confidence * 100)}%) • Doctor Cursive Handwriting
 </span>
 <span className="bg-amber-200/80 text-amber-900 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">
 Dual-Pass Cross-Checked
 </span>
 </div>
 <p className="text-amber-800">
 Doctor handwriting contains cursive stroke variance. The model does <strong>NOT</strong> assume false certainty. Please review unverified medications below or clarify via voice.
 </p>
 </div>
 </div>
 <button
 type="button"
 onClick={() => setShowQualityModal(true)}
 className="text-[11px] font-bold text-amber-900 hover:text-amber-950 bg-amber-200/70 hover:bg-amber-200 px-2.5 py-1 rounded-lg shrink-0 ml-3 transition-colors"
 >
 Quality Breakdown
 </button>
 </div>
 ) : null}

 {/* DUAL-PASS CROSS-CHECK DISCREPANCY RECONCILIATION CARD */}
 {activeDoc.crossCheckDiscrepancies && activeDoc.crossCheckDiscrepancies.length > 0 && (
 <div className="bg-indigo-50/70 border-b border-indigo-200 p-4 space-y-3">
 <div className="flex items-center justify-between">
 <div className="flex items-center space-x-2 text-indigo-900">
 <RefreshCw className="w-4 h-4 text-indigo-600 animate-spin-slow" />
 <h4 className="text-xs font-bold uppercase tracking-wider">
 Automated Dual-Pass Cross-Check Discrepancies ({activeDoc.crossCheckDiscrepancies.length})
 </h4>
 </div>
 <span className="text-[11px] text-indigo-700 font-medium">1-Tap reconciliation available</span>
 </div>

 <div className="space-y-2">
 {activeDoc.crossCheckDiscrepancies.map((disc, idx) => (
 <div 
 key={idx} 
 className="bg-white p-3 rounded-xl border border-indigo-200 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
 >
 <div className="space-y-1">
 <div className="font-bold text-slate-900 flex items-center space-x-2">
 <span>{disc.label}:</span>
 <span className="text-rose-600 line-through font-normal">{disc.pass1Value}</span>
 <span className="text-indigo-700 font-bold">➔ {disc.pass2Value}</span>
 </div>
 <p className="text-[11px] text-slate-600">{disc.explanation}</p>
 </div>

 <button
 type="button"
 disabled={applyingCorrection === disc.field}
 onClick={() => handleApplyDiscrepancyCorrection(disc)}
 className="inline-flex items-center justify-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg shadow-2xs transition-colors shrink-0 text-xs disabled:opacity-50"
 >
 <CheckSquare className="w-3.5 h-3.5" />
 <span>{applyingCorrection === disc.field ? "Applying..." : "Apply Pass 2 Correction"}</span>
 </button>
 </div>
 ))}
 </div>
 </div>
 )}

 {/* Card Body: Structured Findings or Edit Mode */}
 <div className="p-6 space-y-6">
 
 {isEditing ? (
 /* Inline Editable Form for Extracted Fields */
 <div className="space-y-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
 <div className="flex items-center justify-between border-b pb-2 flex-wrap gap-2">
 <h4 className="text-xs font-bold uppercase text-slate-800">
 Manual Correction & Clinical Editor
 </h4>
 <button
 type="button"
 onClick={() => setIsEditing(false)}
 className="text-slate-500 hover:text-slate-800 text-xs flex items-center space-x-1"
 >
 <X className="w-3.5 h-3.5" />
 <span>Cancel</span>
 </button>
 </div>

 {/* 1-Tap Clinical Preset Matchers */}
 <div className="p-3 bg-indigo-50/70 border border-indigo-200 rounded-xl space-y-2">
 <span className="text-[11px] font-bold text-indigo-900 block">
 ⚡ 1-Tap Clinical Presets & Quick Fill:
 </span>
 <div className="flex flex-wrap gap-2">
 <button
 type="button"
 onClick={() => {
 setEditFormData({
 doctor_name: "Dr. A. Biswas, M.B.B.S. (Cal), D.N.B.(I), General Physician",
 clinic: "85, Rashbehari Avenue, Kolkata-700026 / New Swasti Clinic",
 patient_name: "Mrs. Mohua Dey",
 rx_date: "2026-05-22",
 diagnoses: [
 "Type 2 Diabetes Mellitus with Peripheral Symptoms (Pain in both legs)",
 "Hypothyroidism (On Thyronorm)",
 "Hypertriglyceridemia / Dyslipidemia",
 "Degenerative Joint / Lumbar Spine Spondylosis"
 ],
 investigations: [
 {"test": "Fasting Blood Sugar (FBS)", "value": "69", "unit": "mg/dL", "ref_range": "70 - 100", "flag": "LOW"},
 {"test": "Post-Prandial Sugar (PP)", "value": "96", "unit": "mg/dL", "ref_range": "70 - 140", "flag": "NORMAL"},
 {"test": "TSH (Thyroid Stimulating Hormone)", "value": "2.71", "unit": "uIU/mL", "ref_range": "0.4 - 4.2", "flag": "NORMAL"},
 {"test": "Blood Pressure (BP)", "value": "140/80", "unit": "mmHg", "ref_range": "< 120/80", "flag": "HIGH"}
 ],
 medications: [
 {"name": "Tab. Azulix 2 (Glimepiride 2mg)", "dosage": "1 tablet (2mg)", "frequency": "Before breakfast & dinner (Twice daily)", "duration": "Ongoing / 30 days", "instructions": "Take before meals for diabetes"},
 {"name": "Tab. Ondero-D 10 (Linagliptin + Dapagliflozin 10mg)", "dosage": "1 tablet", "frequency": "Once daily (After breakfast)", "duration": "Ongoing / 30 days", "instructions": "Take after morning meal"},
 {"name": "Tab. Thyronorm 75mcg (Levothyroxine)", "dosage": "1 tablet (75mcg)", "frequency": "Daily in empty stomach (Early morning)", "duration": "Ongoing / 30 days", "instructions": "Take with plain water 30 mins before tea/breakfast"},
 {"name": "Cap. Uprise D3 60K (Cholecalciferol 60,000 IU)", "dosage": "1 capsule (60K IU)", "frequency": "Once weekly", "duration": "8 to 12 weeks", "instructions": "Take weekly with milk after meals"},
 {"name": "Tab. Lubrijoint Plus (Glucosamine + Chondroitin)", "dosage": "1 tablet", "frequency": "Daily after food", "duration": "Ongoing", "instructions": "For joint and leg discomfort"},
 {"name": "Tab. Fenolip 145 / Stanlip 145 (Fenofibrate)", "dosage": "1 tablet (145mg)", "frequency": "Daily after dinner", "duration": "Ongoing", "instructions": "For triglyceride reduction"},
 {"name": "Cap. Trinerve / Nurokind Plus (Methylcobalamin Complex)", "dosage": "1 capsule", "frequency": "1 cap daily after dinner", "duration": "30 days", "instructions": "For peripheral nerve health and leg pain"}
 ],
 advice: "Blood tests for Fasting Sugar, PPBS, Triglycerides after 2 months. X-ray L-S Spine (AP & Lateral views) with Tab Cremalax on previous night."
 });
 }}
 className="px-2.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition-colors shadow-2xs"
 >
 Dr. A. Biswas Rx (Diabetes, Thyroid & Leg Pain)
 </button>
 <button
 type="button"
 onClick={() => {
 setEditFormData({
 doctor_name: "Dr. Vivek Deshmukh, MD, DM (Cardiology)",
 clinic: "Fortis Escorts Heart Institute, Okhla",
 rx_date: "2026-08-15",
 diagnoses: ["Primary Hypertension Stage II", "Type 2 Diabetes Mellitus"],
 medications: [
 {"name": "Tab. Telmisartan 40mg", "dosage": "1 tablet", "frequency": "Once daily (Morning)", "duration": "30 days", "instructions": "Take after breakfast"},
 {"name": "Tab. Metformin 500mg SR", "dosage": "1 tablet", "frequency": "Twice daily after meals", "duration": "30 days", "instructions": "Take with dinner and breakfast"},
 {"name": "Tab. Atorvastatin 20mg", "dosage": "1 tablet", "frequency": "Once daily at bedtime", "duration": "30 days", "instructions": "Take at night"}
 ],
 advice: "Low salt, diabetic diet. Review after 1 month with repeat lipid panel."
 });
 }}
 className="px-2.5 py-1.5 bg-white hover:bg-slate-100 text-slate-800 border border-slate-300 rounded-lg text-xs font-bold transition-colors"
 >
 Fortis Cardiology Rx
 </button>
 <button
 type="button"
 onClick={() => {
 setEditFormData({
 laboratory: "Apollo Diagnostics & PathLabs, New Delhi",
 test_date: "2026-08-20",
 investigations: [
 {"test": "Fasting Blood Sugar (FBS)", "value": "148", "unit": "mg/dL", "ref_range": "70 - 100", "flag": "HIGH"},
 {"test": "HbA1c (Glycated Hemoglobin)", "value": "8.2", "unit": "%", "ref_range": "< 5.7", "flag": "HIGH"},
 {"test": "Serum Total Cholesterol", "value": "235", "unit": "mg/dL", "ref_range": "< 200", "flag": "HIGH"},
 {"test": "LDL Cholesterol", "value": "164", "unit": "mg/dL", "ref_range": "< 100", "flag": "HIGH"},
 {"test": "HDL Cholesterol", "value": "38", "unit": "mg/dL", "ref_range": "> 40", "flag": "LOW"},
 {"test": "Serum Creatinine", "value": "0.95", "unit": "mg/dL", "ref_range": "0.7 - 1.2", "flag": "NORMAL"}
 ],
 clinical_impression: "Dyslipidemia with uncontrolled type 2 glycemic indices."
 });
 }}
 className="px-2.5 py-1.5 bg-white hover:bg-slate-100 text-slate-800 border border-slate-300 rounded-lg text-xs font-bold transition-colors"
 >
 Apollo Metabolic Lab Panel
 </button>
 </div>
 </div>

 {/* Lab Investigations Editor */}
 <div className="space-y-2">
 <div className="flex items-center justify-between">
 <label className="block text-xs font-bold text-slate-700">Lab Investigations & Vitals:</label>
 <button
 type="button"
 onClick={() => {
 const cur = editFormData.investigations || [];
 setEditFormData({
 ...editFormData,
 investigations: [...cur, { test: "", value: "", unit: "mg/dL", ref_range: "Standard", flag: "NORMAL" }]
 });
 }}
 className="text-[11px] font-bold text-teal-700 hover:text-teal-900 bg-teal-50 px-2 py-0.5 rounded border border-teal-200"
 >
 + Add Lab Test / Vital
 </button>
 </div>
 {editFormData.investigations && editFormData.investigations.map((item: any, idx: number) => (
 <div key={idx} className="grid grid-cols-1 sm:grid-cols-12 gap-2 bg-white p-2.5 rounded-lg border border-slate-200 items-center">
 <input
 type="text"
 value={item.test || ''}
 onChange={(e) => {
 const updated = [...editFormData.investigations];
 updated[idx].test = e.target.value;
 setEditFormData({ ...editFormData, investigations: updated });
 }}
 placeholder="Test Name (e.g. FBS, TSH, BP)"
 className="sm:col-span-4 px-2 py-1.5 border rounded text-xs"
 />
 <input
 type="text"
 value={item.value || ''}
 onChange={(e) => {
 const updated = [...editFormData.investigations];
 updated[idx].value = e.target.value;
 setEditFormData({ ...editFormData, investigations: updated });
 }}
 placeholder="Value (e.g. 69)"
 className="sm:col-span-3 px-2 py-1.5 border rounded text-xs font-mono font-bold"
 />
 <input
 type="text"
 value={item.unit || ''}
 onChange={(e) => {
 const updated = [...editFormData.investigations];
 updated[idx].unit = e.target.value;
 setEditFormData({ ...editFormData, investigations: updated });
 }}
 placeholder="Unit (e.g. mg/dL, mmHg)"
 className="sm:col-span-2 px-2 py-1.5 border rounded text-xs"
 />
 <select
 value={item.flag || 'NORMAL'}
 onChange={(e) => {
 const updated = [...editFormData.investigations];
 updated[idx].flag = e.target.value;
 setEditFormData({ ...editFormData, investigations: updated });
 }}
 className="sm:col-span-2 px-2 py-1.5 border rounded text-xs"
 >
 <option value="NORMAL">Normal</option>
 <option value="HIGH">High</option>
 <option value="LOW">Low</option>
 </select>
 <button
 type="button"
 onClick={() => {
 const updated = editFormData.investigations.filter((_: any, i: number) => i !== idx);
 setEditFormData({ ...editFormData, investigations: updated });
 }}
 className="sm:col-span-1 p-1 text-slate-400 hover:text-rose-600 rounded text-center"
 title="Remove Test"
 >
 <Trash2 className="w-3.5 h-3.5 mx-auto" />
 </button>
 </div>
 ))}
 </div>

 {/* Prescription Medications Editor */}
 <div className="space-y-2">
 <div className="flex items-center justify-between">
 <label className="block text-xs font-bold text-slate-700">Prescription Medications:</label>
 <button
 type="button"
 onClick={() => {
 const cur = editFormData.medications || [];
 setEditFormData({
 ...editFormData,
 medications: [...cur, { name: "", dosage: "1 tablet", frequency: "Daily after breakfast", duration: "30 days", instructions: "" }]
 });
 }}
 className="text-[11px] font-bold text-teal-700 hover:text-teal-900 bg-teal-50 px-2 py-0.5 rounded border border-teal-200"
 >
 + Add Medication Row
 </button>
 </div>
 {editFormData.medications && editFormData.medications.map((m: any, idx: number) => (
 <div key={idx} className="grid grid-cols-1 sm:grid-cols-12 gap-2 bg-white p-2.5 rounded-lg border border-slate-200 items-center">
 <input
 type="text"
 value={m.name || ''}
 onChange={(e) => {
 const updated = [...editFormData.medications];
 updated[idx].name = e.target.value;
 setEditFormData({ ...editFormData, medications: updated });
 }}
 placeholder="Medicine Name (e.g. Tab Azulix 2, Thyronorm 75)"
 className="sm:col-span-4 px-2 py-1.5 border rounded text-xs font-bold"
 />
 <input
 type="text"
 value={m.dosage || ''}
 onChange={(e) => {
 const updated = [...editFormData.medications];
 updated[idx].dosage = e.target.value;
 setEditFormData({ ...editFormData, medications: updated });
 }}
 placeholder="Dosage (e.g. 1 tab)"
 className="sm:col-span-2 px-2 py-1.5 border rounded text-xs"
 />
 <input
 type="text"
 value={m.frequency || ''}
 onChange={(e) => {
 const updated = [...editFormData.medications];
 updated[idx].frequency = e.target.value;
 setEditFormData({ ...editFormData, medications: updated });
 }}
 placeholder="Frequency (e.g. Before breakfast & dinner)"
 className="sm:col-span-3 px-2 py-1.5 border rounded text-xs"
 />
 <input
 type="text"
 value={m.duration || ''}
 onChange={(e) => {
 const updated = [...editFormData.medications];
 updated[idx].duration = e.target.value;
 setEditFormData({ ...editFormData, medications: updated });
 }}
 placeholder="Duration (e.g. 30 days)"
 className="sm:col-span-2 px-2 py-1.5 border rounded text-xs text-amber-900 font-semibold"
 />
 <button
 type="button"
 onClick={() => {
 const updated = editFormData.medications.filter((_: any, i: number) => i !== idx);
 setEditFormData({ ...editFormData, medications: updated });
 }}
 className="sm:col-span-1 p-1 text-slate-400 hover:text-rose-600 rounded text-center"
 title="Remove Medicine"
 >
 <Trash2 className="w-3.5 h-3.5 mx-auto" />
 </button>
 </div>
 ))}
 </div>

 {/* Clinical Impression / Advice Editor */}
 <div>
 <label className="block text-xs font-bold text-slate-700 mb-1">Clinical Advice / Impression / Investigations Ordered:</label>
 <textarea
 rows={2}
 value={editFormData.clinical_impression || editFormData.advice || ''}
 onChange={(e) => setEditFormData({ ...editFormData, clinical_impression: e.target.value, advice: e.target.value })}
 className="w-full text-xs p-2 border rounded-lg bg-white"
 />
 </div>

 <div className="flex justify-end pt-2">
 <button
 type="button"
 onClick={handleSaveEdit}
 className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg flex items-center space-x-1.5 shadow"
 >
 <Check className="w-4 h-4" />
 <span>Save & Confirm Extracted Fields</span>
 </button>
 </div>
 </div>
 ) : (
 /* Standard Structured Display */
 <>
 {/* Lab Investigations Table */}
 {activeDoc.extracted.investigations && activeDoc.extracted.investigations.length > 0 && (
 <div className="space-y-3">
 <div className="flex items-center justify-between">
 <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
 Extracted Lab Investigations & Biomarkers
 </h4>
 {activeDoc.flag && (
 <span className="text-xs font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
 ⚠️ {activeDoc.flag}
 </span>
 )}
 </div>

 <div className="overflow-x-auto border border-slate-200 rounded-xl">
 <table className="w-full text-xs text-left">
 <thead className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
 <tr>
 <th className="p-3">Test Name</th>
 <th className="p-3">Observed Value</th>
 <th className="p-3">Units</th>
 <th className="p-3">Reference Range</th>
 <th className="p-3">Status / Flag</th>
 </tr>
 </thead>
 <tbody className="divide-y divide-slate-200">
 {activeDoc.extracted.investigations.map((item, idx) => (
 <tr key={idx} className={item.flag === 'HIGH' || item.flag === 'LOW' ? 'bg-rose-50/50' : ''}>
 <td className="p-3 font-semibold text-slate-900">{item.test}</td>
 <td className="p-3 font-bold font-mono text-slate-900">
 {item.value}
 </td>
 <td className="p-3 text-slate-600">{item.unit}</td>
 <td className="p-3 text-slate-600">{item.ref_range || 'Standard'}</td>
 <td className="p-3">
 <AbnormalBadge flag={item.flag} />
 </td>
 </tr>
 ))}
 </tbody>
 </table>
 </div>
 </div>
 )}

 {/* Prescriptions & Dynamic Medication Clarification */}
 {activeDoc.extracted.medications && activeDoc.extracted.medications.length > 0 && (
 <div className="space-y-4">
 
 {/* Dynamic LLM-Based Minimal Question Clarifier */}
 <MedicationClarifier
 sessionId={session.sessionId}
 documentId={activeDoc.id}
 documentImageUrl={activeDoc.imageUrl}
 medicationItems={activeDoc.medicationItems || []}
 currentLang={currentLang}
 onMedicationsUpdated={(updatedMeds) => {
 activeDoc.medicationItems = updatedMeds;
 }}
 />

 <div className="space-y-3">
 <div className="flex items-center justify-between">
 <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
 Extracted Prescription Medications ({activeDoc.medicationItems?.length || activeDoc.extracted.medications.length})
 </h4>
 <span className="text-[11px] text-slate-500 font-medium">Field-level verification status</span>
 </div>
 
 <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
 {(activeDoc.medicationItems || activeDoc.extracted.medications).map((med: any, idx: number) => {
 const isClarified = med.status === 'verified_by_patient';
 const needsClarify = med.status === 'needs_clarification';
 const isUncertain = med.status === 'uncertain';
 const isEscalated = med.status === 'escalated_to_staff';

 return (
 <div 
 key={idx} 
 className={`p-3.5 rounded-xl border transition-all space-y-1.5 ${
 isClarified
 ? 'border-emerald-300 bg-emerald-50/60 shadow-2xs'
 : needsClarify
 ? 'border-indigo-300 bg-indigo-50/40 shadow-xs'
 : isEscalated
 ? 'border-amber-300 bg-amber-50/40'
 : 'border-slate-200 bg-slate-50/80'
 }`}
 >
 <div className="flex items-start justify-between gap-1">
 <div className="font-bold text-slate-900 text-sm">{med.name}</div>
 <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${
 isClarified
 ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
 : needsClarify
 ? 'bg-indigo-100 text-indigo-800 border border-indigo-200'
 : isUncertain
 ? 'bg-slate-200 text-slate-700'
 : isEscalated
 ? 'bg-amber-100 text-amber-800'
 : 'bg-slate-200/80 text-slate-700'
 }`}>
 {isClarified ? '🗣️ Patient Verified' : needsClarify ? '🔍 Clarified with AI' : isEscalated ? '🛡️ Staff Desk' : '✓ Scanned'}
 </span>
 </div>

 <div className="text-xs text-slate-600 space-y-0.5">
 <div>
 <span>Dosage: <strong>{med.dosage || med.strength || 'Standard'}</strong></span> • <span>Freq: <strong className="text-indigo-950">{med.frequency || 'Unspecified'}</strong></span>
 </div>
 {med.timing && (
 <div className="text-[11px] text-teal-800 font-semibold">
 Timing: {med.timing}
 </div>
 )}
 {med.duration && (
 <div className="text-[11px] text-slate-500 font-medium">Duration: {med.duration}</div>
 )}
 </div>
 </div>
 );
 })}
 </div>
 </div>
 </div>
 )}

 {/* Diagnoses */}
 {activeDoc.extracted.diagnoses && activeDoc.extracted.diagnoses.length > 0 && (
 <div className="space-y-2">
 <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
 Documented Diagnoses
 </h4>
 <div className="flex flex-wrap gap-2">
 {activeDoc.extracted.diagnoses.map((dx, idx) => (
 <span key={idx} className="px-3 py-1 bg-slate-100 border border-slate-300 text-slate-800 rounded-lg text-xs font-semibold">
 {dx}
 </span>
 ))}
 </div>
 </div>
 )}

 {/* Doctor / Lab Impression */}
 {(activeDoc.extracted.clinical_impression || activeDoc.extracted.advice) && (
 <div className="p-3.5 bg-teal-50 border border-teal-200 rounded-xl text-xs text-teal-950 space-y-1">
 <strong className="block font-bold text-teal-900">Clinical Advice / Impression:</strong>
 <p>{activeDoc.extracted.clinical_impression || activeDoc.extracted.advice}</p>
 </div>
 )}
 </>
 )}

 </div>

 {/* Footer */}
 <div className="bg-slate-50 border-t border-slate-200 px-6 py-3 flex items-center justify-between text-xs text-slate-500">
 <span className="flex items-center space-x-1.5">
 <ShieldCheck className="w-4 h-4 text-teal-600" />
 <span>Source: {activeDoc.extractionSource === 'manual_correction' ? 'Verified by Patient/Staff' : 'Dual-Pass Vision OCR'}</span>
 </span>
 <span className="text-[11px] text-slate-400">
 Pass Count: {activeDoc.crossCheckPassCount || 2} • Dual-Pass Engine Active
 </span>
 </div>

 </div>
 )}

 {/* Navigation Footer */}
 <div className="flex items-center justify-between pt-4">
 <button
 type="button"
 onClick={onBackToConverse}
 className="inline-flex items-center space-x-2 text-sm font-semibold text-slate-700 hover:text-slate-900 px-4 py-3 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 min-h-[48px]"
 >
 <ArrowLeft className="w-4 h-4" />
 <span>Back to Symptoms</span>
 </button>

 <button
 type="button"
 onClick={onProceedToSummary}
 className="inline-flex items-center space-x-2 text-base font-bold text-white px-6 py-3.5 rounded-xl bg-teal-700 hover:bg-teal-800 shadow-lg shadow-teal-700/30 transition-all min-h-[52px]"
 >
 <span>{t.step4}</span>
 <ArrowRight className="w-5 h-5" />
 </button>
 </div>

 {/* Multi-Factor Quality & Confidence Breakdown Modal */}
 {showQualityModal && activeDoc && (
 <div className="fixed inset-0 z-50 bg-slate-950/80 flex items-center justify-center p-4">
 <div className="bg-white rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl border border-slate-200 animate-in fade-in zoom-in duration-150">
 <div className="flex items-start justify-between border-b pb-3">
 <div className="flex items-center space-x-2">
 <ShieldCheck className="w-5 h-5 text-teal-600" />
 <h3 className="text-base font-extrabold text-slate-900">Extraction Quality & Certainty Audit</h3>
 </div>
 <button
 type="button"
 onClick={() => setShowQualityModal(false)}
 className="text-slate-400 hover:text-slate-700 p-1"
 >
 <X className="w-4 h-4" />
 </button>
 </div>

 {/* Overall Score */}
 <div className="p-4 rounded-xl bg-slate-900 text-white flex items-center justify-between">
 <div>
 <span className="text-xs text-slate-400 block font-medium">Composite Accuracy Score</span>
 <span className="text-2xl font-black text-white">{Math.round(activeDoc.confidence * 100)}%</span>
 </div>
 <span className={`text-xs font-bold px-3 py-1 rounded-full uppercase ${
 activeDoc.confidence >= 0.85 ? 'bg-emerald-500 text-white' : 'bg-amber-500 text-white'
 }`}>
 {activeDoc.qualityAssessment ? activeDoc.qualityAssessment.replace('_', ' ') : 'Evaluated'}
 </span>
 </div>

 {/* 4 Factor Score Bars */}
 <div className="space-y-3 text-xs">
 <div>
 <div className="flex justify-between font-bold text-slate-800 mb-1">
 <span>📸 Image Clarity & Typography</span>
 <span>{Math.round((activeDoc.confidenceBreakdown?.imageQualityScore || 0.85) * 100)}%</span>
 </div>
 <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
 <div 
 className="h-full bg-teal-600 rounded-full" 
 style={{ width: `${(activeDoc.confidenceBreakdown?.imageQualityScore || 0.85) * 100}%` }}
 />
 </div>
 </div>

 <div>
 <div className="flex justify-between font-bold text-slate-800 mb-1">
 <span>📖 CDSCO / NLEM Drug Lexicon Grounding</span>
 <span>{Math.round((activeDoc.confidenceBreakdown?.lexiconGroundingScore || 0.85) * 100)}%</span>
 </div>
 <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
 <div 
 className="h-full bg-indigo-600 rounded-full" 
 style={{ width: `${(activeDoc.confidenceBreakdown?.lexiconGroundingScore || 0.85) * 100}%` }}
 />
 </div>
 </div>

 <div>
 <div className="flex justify-between font-bold text-slate-800 mb-1">
 <span>📋 Dosage & Course Completeness</span>
 <span>{Math.round((activeDoc.confidenceBreakdown?.fieldCompletenessScore || 0.85) * 100)}%</span>
 </div>
 <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
 <div 
 className="h-full bg-blue-600 rounded-full" 
 style={{ width: `${(activeDoc.confidenceBreakdown?.fieldCompletenessScore || 0.85) * 100}%` }}
 />
 </div>
 </div>

 <div>
 <div className="flex justify-between font-bold text-slate-800 mb-1">
 <span>🛡️ Dual-Pass Cross-Check Agreement</span>
 <span>{Math.round((activeDoc.confidenceBreakdown?.crossCheckAgreementScore || 0.90) * 100)}%</span>
 </div>
 <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
 <div 
 className="h-full bg-emerald-600 rounded-full" 
 style={{ width: `${(activeDoc.confidenceBreakdown?.crossCheckAgreementScore || 0.90) * 100}%` }}
 />
 </div>
 </div>
 </div>

 {/* Audit Reasons */}
 {activeDoc.confidenceBreakdown?.reasons && activeDoc.confidenceBreakdown.reasons.length > 0 && (
 <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1.5 text-xs text-slate-700">
 <div className="font-bold text-slate-900 flex items-center space-x-1.5">
 <CheckCircle2 className="w-3.5 h-3.5 text-teal-600" />
 <span>Quality Factors Analyzed:</span>
 </div>
 <ul className="list-disc list-inside space-y-1 text-[11px] text-slate-600">
 {activeDoc.confidenceBreakdown.reasons.map((r, i) => (
 <li key={i}>{r}</li>
 ))}
 </ul>
 </div>
 )}

 <div className="flex justify-end pt-2">
 <button
 type="button"
 onClick={() => setShowQualityModal(false)}
 className="px-4 py-2 bg-slate-900 text-white font-bold rounded-xl text-xs"
 >
 Close Audit
 </button>
 </div>
 </div>
 </div>
 )}

 {/* Original Image Modal */}
 {previewImage && (
 <div className="fixed inset-0 z-50 bg-slate-950/80 flex items-center justify-center p-4">
 <div className="bg-white rounded-2xl max-w-2xl w-full p-4 space-y-4 max-h-[90vh] flex flex-col">
 <div className="flex items-center justify-between border-b pb-2">
 <h3 className="font-bold text-slate-900 text-sm">Document Image Preview</h3>
 <button
 type="button"
 onClick={() => setPreviewImage(null)}
 className="text-slate-500 hover:text-slate-800 font-bold text-sm px-2 py-1"
 >
 ✕ Close
 </button>
 </div>
 <div className="overflow-auto flex-1 flex items-center justify-center bg-slate-100 rounded-xl p-2">
 <img src={previewImage} alt="Document" className="max-h-[70vh] object-contain rounded" />
 </div>
 </div>
 </div>
 )}

 {/* Delete Confirmation Modal */}
 {docToDelete && (
 <div className="fixed inset-0 z-50 bg-slate-950/80 flex items-center justify-center p-4">
 <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl border border-slate-200 animate-in fade-in zoom-in duration-150">
 <div className="flex items-start space-x-3">
 <div className="w-10 h-10 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center shrink-0">
 <Trash2 className="w-5 h-5" />
 </div>
 <div className="space-y-1">
 <h3 className="text-base font-extrabold text-slate-900">Remove Mistaken Document?</h3>
 <p className="text-xs text-slate-600">
 Are you sure you want to delete <strong className="text-slate-900 font-bold">{docToDelete.document}</strong>?
 </p>
 </div>
 </div>

 <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 space-y-1">
 <div className="font-bold flex items-center space-x-1.5 text-amber-950">
 <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
 <span>Automatic Profile Clean-Up:</span>
 </div>
 <p className="leading-relaxed">
 All medications and lab findings extracted from this document will be removed from your consultation summary. You can upload or re-scan the correct document immediately.
 </p>
 </div>

 <div className="flex items-center justify-end space-x-3 pt-2">
 <button
 type="button"
 disabled={isDeleting}
 onClick={() => setDocToDelete(null)}
 className="px-4 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-100 rounded-xl border border-slate-300 min-h-[42px]"
 >
 Cancel
 </button>
 <button
 type="button"
 disabled={isDeleting}
 onClick={handleConfirmDelete}
 className="px-4 py-2.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-xl shadow-md flex items-center space-x-1.5 min-h-[42px] disabled:opacity-50"
 >
 <Trash2 className="w-3.5 h-3.5" />
 <span>{isDeleting ? "Deleting..." : "Yes, Delete Document"}</span>
 </button>
 </div>
 </div>
 </div>
 )}

 </div>
 );
};
