import React, { useRef } from 'react';
import { 
  Printer, X, Download, ShieldCheck, QrCode, 
  Building2, Stethoscope, User, Calendar, FileText, CheckCircle2
} from 'lucide-react';
import { PrescriptionOrder } from '../types';

interface PrescriptionModalProps {
  prescription: PrescriptionOrder;
  onClose: () => void;
}

export const PrescriptionModal: React.FC<PrescriptionModalProps> = ({
  prescription,
  onClose
}) => {
  const printRef = useRef<HTMLDivElement>(null);

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white w-full max-w-4xl rounded-3xl shadow-2xl border border-slate-200 overflow-hidden max-h-[95vh] flex flex-col animate-in fade-in zoom-in duration-200">
        
        {/* Modal Controls Bar (Hidden during Print) */}
        <div className="print:hidden bg-slate-900 text-white px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-teal-500 text-white flex items-center justify-center shadow-md">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold">Official OPD Electronic Prescription Slip</h3>
              <p className="text-xs text-slate-400">Prescription ID: {prescription.prescriptionId} • Ready for Print / Download</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={handlePrint}
              className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-xl flex items-center space-x-1.5 transition-colors shadow-sm"
            >
              <Printer className="w-4 h-4" />
              <span>Print Prescription</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Printable Document Body */}
        <div ref={printRef} className="p-8 overflow-y-auto space-y-6 bg-white text-slate-900 flex-1 print:p-0 print:m-0">
          
          {/* Hospital Letterhead */}
          <div className="border-b-2 border-slate-900 pb-4 flex items-start justify-between">
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <Building2 className="w-6 h-6 text-teal-700" />
                <h1 className="text-xl font-black tracking-tight text-slate-900 uppercase">
                  {prescription.hospitalName}
                </h1>
              </div>
              <p className="text-xs text-slate-600 font-medium">
                Main OPD Block • Ministry of Health & Family Welfare • National Healthcare Network
              </p>
              <p className="text-[11px] text-slate-500">
                Department of {prescription.doctorDepartment} • Ayushman Bharat Digital Mission (ABDM) Integrated
              </p>
            </div>

            <div className="text-right space-y-1">
              <div className="inline-block px-2.5 py-1 bg-slate-100 border border-slate-300 rounded text-xs font-mono font-bold">
                {prescription.prescriptionId}
              </div>
              <div className="text-xs text-slate-600 flex items-center justify-end space-x-1">
                <Calendar className="w-3.5 h-3.5" />
                <span>Date: {prescription.date}</span>
              </div>
            </div>
          </div>

          {/* Doctor & Patient Information Banner */}
          <div className="grid grid-cols-2 gap-4 p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs">
            {/* Patient Column */}
            <div className="space-y-1">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Patient Details</div>
              <div className="text-sm font-bold text-slate-900">{prescription.patientName}</div>
              <div className="text-slate-600 font-medium">
                Age / Gender: <span className="font-bold text-slate-800">{prescription.patientAge} Yrs / {prescription.patientGender}</span>
              </div>
              <div className="text-slate-600">
                ABHA ID: <span className="font-mono font-bold text-teal-800">{prescription.patientAbhaId || 'Not Linked'}</span>
              </div>
            </div>

            {/* Doctor Column */}
            <div className="space-y-1 text-right">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Attending Physician</div>
              <div className="text-sm font-bold text-slate-900">{prescription.doctorName}</div>
              <div className="text-slate-600 font-medium">Reg No: <span className="font-mono font-bold">{prescription.doctorRegNo}</span></div>
              <div className="text-slate-600">{prescription.doctorDepartment}</div>
            </div>
          </div>

          {/* Recorded Vitals Summary */}
          {prescription.vitalsSummary && (
            <div className="px-4 py-2.5 bg-teal-50/70 border border-teal-200 rounded-xl text-xs text-teal-950 flex items-center justify-between">
              <div className="font-bold">Recorded Vitals at Registration:</div>
              <div className="font-mono font-semibold">{prescription.vitalsSummary}</div>
            </div>
          )}

          {/* Clinical Diagnoses & ICD-10 */}
          <div className="space-y-1.5">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-teal-600"></span>
              <span>Clinical Diagnoses & Assessment:</span>
            </div>
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1 text-xs">
              {prescription.diagnoses.map((d, idx) => (
                <div key={idx} className="font-bold text-slate-800 flex items-center justify-between">
                  <span>• {d}</span>
                  {prescription.icd10Codes[idx] && (
                    <span className="text-[11px] font-mono font-semibold text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
                      {prescription.icd10Codes[idx]}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Prescribed Medications (Rx Table) */}
          <div className="space-y-2">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-1.5">
              <span className="text-lg font-serif italic font-bold text-teal-800">℞</span>
              <span>Prescription Pharmacotherapy (Rx):</span>
            </div>
            
            <table className="w-full text-xs text-left border-collapse border border-slate-300">
              <thead>
                <tr className="bg-slate-100 text-slate-800 font-bold border-b border-slate-300">
                  <th className="p-2.5 border-r border-slate-300">#</th>
                  <th className="p-2.5 border-r border-slate-300">Medication & Formulation</th>
                  <th className="p-2.5 border-r border-slate-300">Dosage</th>
                  <th className="p-2.5 border-r border-slate-300">Frequency & Schedule</th>
                  <th className="p-2.5 border-r border-slate-300">Duration</th>
                  <th className="p-2.5">Instructions</th>
                </tr>
              </thead>
              <tbody>
                {prescription.medications.map((m, idx) => (
                  <tr key={idx} className="border-b border-slate-200 hover:bg-slate-50">
                    <td className="p-2.5 font-bold text-slate-500 border-r border-slate-200 text-center">{idx + 1}</td>
                    <td className="p-2.5 font-bold text-slate-900 border-r border-slate-200">
                      <div>{m.name}</div>
                      {m.genericName && <div className="text-[10px] text-slate-500 font-normal">{m.genericName}</div>}
                    </td>
                    <td className="p-2.5 font-mono text-slate-800 border-r border-slate-200">{m.dosage}</td>
                    <td className="p-2.5 text-slate-800 border-r border-slate-200">{m.frequency}</td>
                    <td className="p-2.5 font-semibold text-amber-900 border-r border-slate-200">{m.duration}</td>
                    <td className="p-2.5 text-slate-600 text-[11px]">{m.instructions || m.timing || 'As directed'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Laboratory / Diagnostic Investigations Advised */}
          {prescription.investigationsAdvised && prescription.investigationsAdvised.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-indigo-600"></span>
                <span>Investigations Advised:</span>
              </div>
              <div className="p-3 bg-indigo-50/50 border border-indigo-200 rounded-xl text-xs text-indigo-950 space-y-1">
                {prescription.investigationsAdvised.map((inv, idx) => (
                  <div key={idx} className="font-semibold">• {inv}</div>
                ))}
              </div>
            </div>
          )}

          {/* Dietary & Lifestyle Advice */}
          {prescription.dietaryLifestyleAdvice && (
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-1">
              <div className="font-bold text-slate-800">Dietary & Lifestyle Advice:</div>
              <div className="text-slate-600">{prescription.dietaryLifestyleAdvice}</div>
            </div>
          )}

          {/* Follow Up & Doctor Signature Block */}
          <div className="pt-6 border-t-2 border-slate-200 flex items-end justify-between">
            <div className="space-y-2">
              <div className="text-xs text-slate-700">
                <strong>Next OPD Review / Follow-up:</strong> In <span className="font-bold text-teal-800">{prescription.followUpDays} days</span>
              </div>
              
              {/* QR Code Verification Simulation */}
              <div className="flex items-center space-x-2 pt-1">
                <div className="w-12 h-12 bg-slate-900 text-white rounded-lg flex items-center justify-center p-1">
                  <QrCode className="w-10 h-10 text-teal-400" />
                </div>
                <div className="text-[10px] text-slate-500">
                  <div className="font-bold text-slate-700">Digital ABDM QR Verification</div>
                  <div>Scan to verify prescription authenticity on hospital portal.</div>
                </div>
              </div>
            </div>

            {/* Doctor Signature Stamp */}
            <div className="text-center space-y-1">
              <div className="w-44 border-b border-slate-400 pb-1 mx-auto text-teal-900 font-serif italic text-sm">
                {prescription.doctorName}
              </div>
              <div className="text-[11px] font-bold text-slate-800">{prescription.doctorName}</div>
              <div className="text-[10px] text-slate-500">{prescription.doctorDepartment} • Reg: {prescription.doctorRegNo}</div>
              <div className="text-[9px] text-teal-700 font-bold uppercase tracking-wider flex items-center justify-center space-x-1">
                <CheckCircle2 className="w-3 h-3 text-teal-600" />
                <span>Digitally Signed & Committed</span>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};

