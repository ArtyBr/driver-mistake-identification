import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAnalysesList } from '../hooks/useAnalysesList';
import AnalysisListItem from '../components/common/AnalysisListItem';
import './GuidePage.css';

const SECTIONS = [
  { id: 'overview',  label: 'Overview'           },
  { id: 'setup',     label: 'Equipment Setup'     },
  { id: 'recording', label: 'Recording'           },
  { id: 'uploading', label: 'Uploading & Waiting' },
];

function StepSection({ id, number, title, subtitle, icon, children }) {
  return (
    <section id={id} className="guide-section">
      <div className="guide-section-header">
        <div className="guide-step-badge">{number}</div>
        <div>
          <div className="guide-step-label">
            <i className={`bi ${icon}`}></i>
            <span>Step {number}</span>
          </div>
          <h2 className="guide-section-title">{title}</h2>
          {subtitle && <p className="guide-section-subtitle">{subtitle}</p>}
        </div>
      </div>
      <div className="guide-section-body">{children}</div>
    </section>
  );
}

function SubHeading({ children }) {
  return <h4 className="guide-subheading">{children}</h4>;
}

/** Neutral callout — for general notes (e.g. loop recording) */
function Callout({ children }) {
  return <div className="guide-callout">{children}</div>;
}

/** Amber tip callout — for recommended practices */
function Tip({ children }) {
  return (
    <div className="guide-callout guide-callout-tip">
      <i className="bi bi-lightbulb guide-callout-icon"></i>
      <div>{children}</div>
    </div>
  );
}

/** Blue action box — for key steps the user must actively do */
function ActionBox({ icon, title, children }) {
  return (
    <div className="guide-action-box">
      <div className="guide-action-header">
        <i className={`bi ${icon} guide-action-icon`}></i>
        <strong>{title}</strong>
      </div>
      {children && <p className="text-muted small mb-0 mt-2">{children}</p>}
    </div>
  );
}

function CheckList({ items }) {
  return (
    <ul className="guide-checklist">
      {items.map((item, i) => (
        <li key={i} className="guide-checklist-item">
          <i className="bi bi-check2 guide-check-icon"></i>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function GuidePage() {
  const [activeSection, setActiveSection] = useState('overview');
  const navigate = useNavigate();
  const { analyses } = useAnalysesList();

  const demoAnalysis =
    analyses.find(a => a.is_demo && a.status === 'COMPLETED' && a.name === 'Me to gym turn cut 2') ||
    analyses.find(a => a.is_demo && a.status === 'COMPLETED');

  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => entries.forEach(e => { if (e.isIntersecting) setActiveSection(e.target.id); }),
      { rootMargin: '-10% 0px -60% 0px', threshold: 0 }
    );
    SECTIONS.forEach(s => {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  const scrollTo = (id) => {
    const el = document.getElementById(id);
    if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 80, behavior: 'smooth' });
  };

  return (
    <div className="guide-page">

      <div className="guide-hero">
        <div className="page-header">
          <h1 className="page-title">Getting Started Guide</h1>
          <p className="page-subtitle">Set up your cameras and analyse your driving in four steps</p>
        </div>
      </div>

      <div className="row g-5">

        {/* Sticky TOC */}
        <div className="col-lg-3 d-none d-lg-block">
          <div className="guide-toc-sticky">
            <p className="guide-toc-heading">Contents</p>
            <nav>
              {SECTIONS.map((s, i) => (
                <button
                  key={s.id}
                  className={`guide-toc-btn${activeSection === s.id ? ' active' : ''}`}
                  onClick={() => scrollTo(s.id)}
                >
                  <span className="guide-toc-num">{i + 1}</span>
                  <span>{s.label}</span>
                </button>
              ))}
            </nav>
            <div className="mt-4">
              <Link to="/analyze" className="btn btn-cyber-primary w-100">
                <i className="bi bi-upload me-2"></i>Start Analysis
              </Link>
            </div>
          </div>
        </div>

        <div className="col-lg-9">

          {/* ── 1. OVERVIEW ── */}
          <StepSection id="overview" number={1} icon="bi-cpu"
            title="What SafeDrive AI Does"
            subtitle="How the system analyses your driving"
          >
            <p className="text-muted">
              SafeDrive AI uses machine learning to analyse both your road footage and face data,
              automatically detecting driving mistakes to help you correct them before your driving
              test.
            </p>
            <p className="text-muted mb-4">
              By cross-referencing your eye movements and head pose against detected lane changes
              and turns, the system determines whether you performed the required mirror checks at
              the right moments. Currently, it detects <strong>left and right lane changes</strong>,{' '}
              <strong>left and right turns</strong>, and evaluates the mirror observations made
              before each.
            </p>

            <SubHeading>See It in Action</SubHeading>
            <p className="text-muted mb-3">
              Click the example below to explore a real analysis. This is the same view you'll see for
              your own sessions.
            </p>
            {demoAnalysis ? (
              <>
                <AnalysisListItem
                  analysis={demoAnalysis}
                  onClick={() => navigate(`/view/${demoAnalysis.id}`)}
                />
                <p className="text-muted small mt-2">
                  <i className="bi bi-arrow-right me-1"></i>
                  Click to open the full results viewer with dual-video playback and event timeline.
                </p>
              </>
            ) : (
              <div className="text-muted small py-3 text-center" style={{ border: '1px solid var(--border-color)', borderRadius: 6 }}>
                <span className="spinner-border spinner-border-sm me-2 opacity-50" role="status"></span>
                Loading demo…
              </div>
            )}
          </StepSection>

          {/* ── 2. SETUP ── */}
          <StepSection id="setup" number={2} icon="bi-camera-video"
            title="Equipment Setup"
            subtitle="What you need and how to configure it"
          >
            <SubHeading>Road-Facing Dash-Cam</SubHeading>
            <p className="text-muted">
              A road-facing dash-cam is <strong>required</strong> to detect lane changes and turns.
              Mount it securely on the windscreen, ideally centred behind the rear-view mirror,
              so both lane markings are clearly visible. Record in at least 1080p where possible,
              and make sure you know how to download footage afterwards (via SD card or Wi-Fi).
            </p>

            <SubHeading>Driver-Facing Camera</SubHeading>
            <p className="text-muted mb-3">
              The system also needs footage of your face to analyse gaze and head movements.
              You have two options:
            </p>

            <div className="row g-3 mb-3">
              <div className="col-sm-6">
                <div className="guide-option-card guide-option-preferred">
                  <div className="guide-option-label">Preferred</div>
                  <i className="bi bi-camera-video guide-option-icon"></i>
                  <div className="guide-option-title">Internal Dash-Cam</div>
                  <p className="text-muted small mb-0">
                    If your dash-cam has a cabin-facing lens, use it. No phone needed as both
                    streams download from the same device.
                  </p>
                </div>
              </div>
              <div className="col-sm-6">
                <div className="guide-option-card">
                  <div className="guide-option-label guide-option-label-alt">Alternative</div>
                  <i className="bi bi-phone guide-option-icon"></i>
                  <div className="guide-option-title">Smartphone</div>
                  <p className="text-muted small mb-0">
                    Mount your phone so it faces you and records throughout the drive (see
                    the note below about background recording).
                  </p>
                </div>
              </div>
            </div>

            <Callout>
              The default camera app on most phones stops recording when minimised or when the
              screen turns off. If you want to use navigation or keep the screen off during the
              drive, we recommend installing an app that supports background video recording,
              such as <strong>Background Video Recorder</strong> on Android. Search your app
              store for a suitable option before your drive.
            </Callout>

            <SubHeading>Phone Placement</SubHeading>
            <p className="text-muted">
              Position your phone (or internal camera) so your face is clearly visible across{' '}
              <strong>all mirror-check directions</strong>, including glances left, right, and
              up to the rear-view mirror.
            </p>
            <Tip>
              We recommend an adjustable mount on the dashboard or air vent to keep the phone
              stable throughout the journey. All non-driver faces are automatically blurred, so
              you don't need to worry about passengers being in frame.
            </Tip>

            <div className="guide-image-placeholder">
              <i className="bi bi-image guide-placeholder-icon"></i>
              <span className="guide-placeholder-label">Example phone mount (image coming soon)</span>
            </div>
          </StepSection>

          {/* ── 3. RECORDING ── */}
          <StepSection id="recording" number={3} icon="bi-record-circle"
            title="Recording a Session"
            subtitle="What to do before and at the start of your drive"
          >
            <SubHeading>Before You Set Off</SubHeading>
            <p className="text-muted">
              Make sure <strong>both cameras are running</strong> before you move off. Many
              dash-cams start automatically when the engine turns on; your driver-facing app
              will need to be started manually. Confirm both feeds are active before driving.
            </p>

            <SubHeading>
              Synchronising the Two Videos{' '}
              <span className="guide-subheading-note">
                (phone + dash-cam setups only)
              </span>
            </SubHeading>
            <p className="text-muted mb-3">
              When using a separate phone as the driver-facing camera, the two devices start
              independently, so the system needs a reference point to align their timelines.
              If your dash-cam has a built-in cabin-facing lens, both streams come from the
              same device and are already synchronised, so you can skip this step.
            </p>
            <ActionBox icon="bi-hand-index-thumb" title="Clap once, clearly, at the start of the recording">
              Make sure it's visible to the driver-facing camera. The sharp audio spike and
              corresponding visual movement let the system sync the two streams automatically.
            </ActionBox>

            <SubHeading>
              Calibration Look{' '}
              <span className="guide-subheading-note">
                (recommended for first recordings or new camera positions)
              </span>
            </SubHeading>
            <p className="text-muted mb-3">
              If this is your first recording, or you've changed your camera position since your
              last session, perform this sequence while safely stationary at the start of the drive:
            </p>
            <ActionBox icon="bi-eye" title="Look at each mirror for ~3 seconds, then look forward">
              Left mirror → Rear-view mirror → Right mirror → Forward.
              Hold your gaze steadily at each position.
            </ActionBox>
            <Callout>
              SafeDrive AI builds a <strong>personalised gaze model</strong> from your face and
              camera setup. Without calibration footage, the system uses a generic model which
              may be less accurate. Once you upload a video with calibration footage, you can
              generate a personal calibration profile from the Results page and apply it to all
              future uploads.
            </Callout>
          </StepSection>

          {/* ── 4. UPLOADING ── */}
          <StepSection id="uploading" number={4} icon="bi-cloud-upload"
            title="Downloading & Uploading Your Videos"
            subtitle="Getting your footage into SafeDrive AI"
          >
            <SubHeading>Download Your Dash-Cam Footage</SubHeading>
            <p className="text-muted">
              When your session is complete, download the road-facing footage from your dash-cam
              either by removing the SD card and copying files to your computer, or wirelessly
              via your dash-cam's companion app if it supports Wi-Fi transfer.
            </p>
            <Callout>
              Most dash-cams use <strong>loop recording</strong>, splitting footage into short
              clips (e.g. 1-3 minute segments). This is fine: upload all clips together and
              SafeDrive AI will automatically splice and synchronise them with your driver-facing
              footage.
            </Callout>

            <SubHeading>Upload via the Analyse Page</SubHeading>
            <p className="text-muted mb-2">
              Head to the{' '}
              <Link to="/analyze" className="guide-link">Analyse Video</Link> page and:
            </p>
            <CheckList items={[
              'Select your road-facing video files (multiple clips from loop recording are supported)',
              'Select your driver-facing video file',
              'Optionally select a calibration profile if you have generated one previously',
              "Give the session a name, or leave it to default to the first file's name",
              'Choose whether automatic video synchronisation is needed',
              'Click Upload and wait for confirmation',
            ]} />

            <SubHeading>Waiting for Analysis</SubHeading>
            <p className="text-muted">
              Analysis can take several minutes. You <strong>do not need to stay on the upload
              page</strong>. Your session will appear in your analysis list on the Home page
              with a live progress indicator. Once complete, click it to view your full results.
            </p>
          </StepSection>

          {/* CTA */}
          <div className="guide-cta-section">
            <div className="guide-cta-card">
              <h3 className="guide-cta-title">Ready to analyse your driving?</h3>
              <p className="text-muted mb-4">
                Set up your cameras, record a session, and upload it to get your first safety report.
              </p>
              <div className="d-flex gap-3 flex-wrap justify-content-center">
                <Link to="/analyze" className="btn btn-cyber-primary">
                  <i className="bi bi-upload me-2"></i>Upload a Session
                </Link>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

export default GuidePage;
