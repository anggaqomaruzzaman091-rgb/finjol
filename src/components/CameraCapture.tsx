import { useRef, useState, useEffect } from 'react';
import { Camera, X, RefreshCw } from 'lucide-react';

interface CameraCaptureProps {
  onCapture: (file: File) => void;
  onCancel: () => void;
}

export default function CameraCapture({ onCapture, onCancel }: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Use a ref for the stream so stopCamera never changes identity
  const streamRef = useRef<MediaStream | null>(null);
  const [error, setError] = useState<string>('');

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  };

  const startCamera = async () => {
    stopCamera();
    try {
      setError('');
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      });
      streamRef.current = mediaStream;
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch {
      setError('Camera access denied or unavailable. Please ensure permissions are granted.');
    }
  };

  // Empty deps — run once on mount, clean up on unmount
  useEffect(() => {
    startCamera();
    return () => stopCamera();
  }, []);

  const handleCapture = () => {
    if (videoRef.current && canvasRef.current) {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      
      // Set canvas dimension to match video frame exactly
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        canvas.toBlob((blob) => {
          if (blob) {
            stopCamera();
            const file = new File([blob], 'id_scan_capture.jpg', { type: 'image/jpeg' });
            onCapture(file);
          }
        }, 'image/jpeg', 0.92);
      }
    }
  };

  return (
    <div style={{ position: 'relative', width: '100%', borderRadius: '8px', overflow: 'hidden', background: '#000', border: '2px solid var(--accent-cyan)' }}>
      {error ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#ff4d4f' }}>
          <p>{error}</p>
          <button className="btn-secondary" onClick={onCancel} style={{ marginTop: '1rem' }}>Cancel</button>
        </div>
      ) : (
        <>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{ width: '100%', display: 'block', backgroundColor: '#111' }}
          />
          <canvas ref={canvasRef} style={{ display: 'none' }} />
          
          {/* Scanning Box Reticle Overlay */}
          <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
             <div style={{
                position: 'absolute', top: '15%', left: '10%', width: '80%', height: '70%', 
                border: '2px solid rgba(0, 255, 255, 0.5)', borderRadius: '12px', boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.5)'
             }}>
                <div style={{ position: 'absolute', top: -2, left: -2, width: 20, height: 20, borderTop: '4px solid #00ffff', borderLeft: '4px solid #00ffff' }}></div>
                <div style={{ position: 'absolute', top: -2, right: -2, width: 20, height: 20, borderTop: '4px solid #00ffff', borderRight: '4px solid #00ffff' }}></div>
                <div style={{ position: 'absolute', bottom: -2, left: -2, width: 20, height: 20, borderBottom: '4px solid #00ffff', borderLeft: '4px solid #00ffff' }}></div>
                <div style={{ position: 'absolute', bottom: -2, right: -2, width: 20, height: 20, borderBottom: '4px solid #00ffff', borderRight: '4px solid #00ffff' }}></div>
             </div>
             <p style={{ position: 'absolute', bottom: '15%', width: '100%', textAlign: 'center', color: '#fff', fontSize: '0.85rem', textShadow: '1px 1px 4px #000' }}>Position KTP/Passport within the frame</p>
          </div>

          <div style={{ position: 'absolute', bottom: '1rem', width: '100%', display: 'flex', justifyContent: 'center', gap: '1rem', padding: '0 1rem' }}>
            <button 
              onClick={onCancel}
              style={{ background: 'rgba(255,255,255,0.2)', border: 'none', padding: '0.8rem', borderRadius: '50%', cursor: 'pointer', color: '#fff', backdropFilter: 'blur(5px)' }}
              title="Cancel"
            >
              <X size={24} />
            </button>
            <button 
              onClick={handleCapture}
              className="btn-primary"
              style={{ padding: '0.8rem 2rem', display: 'flex', alignItems: 'center', gap: '0.5rem', boxShadow: '0 4px 15px rgba(0, 255, 255, 0.3)' }}
            >
              <Camera size={20} /> Capture
            </button>
            <button 
              onClick={startCamera}
              style={{ background: 'rgba(255,255,255,0.2)', border: 'none', padding: '0.8rem', borderRadius: '50%', cursor: 'pointer', color: '#fff', backdropFilter: 'blur(5px)' }}
              title="Restart Camera"
            >
              <RefreshCw size={24} />
            </button>
          </div>
        </>
      )}
    </div>
  );
}
