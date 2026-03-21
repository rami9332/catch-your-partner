import AVFoundation
import UIKit
import Vision

final class CameraScanViewController: UIViewController, AVCaptureVideoDataOutputSampleBufferDelegate, AVCaptureMetadataOutputObjectsDelegate {
    private enum ScanPhase {
        case scanning
        case result
    }

    private enum LivenessStep {
        case straight
        case left
        case right
        case complete
    }

    private let session = AVCaptureSession()
    private let sessionQueue = DispatchQueue(label: "com.catchyourpartner.camera-scan.session")
    private let videoOutput = AVCaptureVideoDataOutput()
    private let metadataOutput = AVCaptureMetadataOutput()
    private let previewView = UIView()
    private let overlayCard = UIView()
    private let titleLabel = UILabel()
    private let bodyLabel = UILabel()
    private let activityIndicator = UIActivityIndicatorView(style: .large)
    private let primaryButton = UIButton(type: .system)
    private let secondaryButton = UIButton(type: .system)
    private let closeButton = UIButton(type: .system)

    private var latestSampleBuffer: CMSampleBuffer?
    private var didConfigureSession = false
    private var captureScheduled = false
    private var didFinish = false
    private var phase: ScanPhase = .scanning
    private var currentLivenessStep: LivenessStep = .straight
    private var stableFrames = 0
    private let stableFrameThreshold = 4

    private let completion: (CameraScanCoordinator.ScanResult) -> Void

    init(completion: @escaping (CameraScanCoordinator.ScanResult) -> Void) {
        self.completion = completion
        super.init(nibName: nil, bundle: nil)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black

        previewView.translatesAutoresizingMaskIntoConstraints = false
        previewView.backgroundColor = .black
        view.addSubview(previewView)

        closeButton.translatesAutoresizingMaskIntoConstraints = false
        closeButton.setTitle("Schliessen", for: .normal)
        closeButton.setTitleColor(UIColor(red: 0.98, green: 0.94, blue: 0.89, alpha: 1.0), for: .normal)
        closeButton.titleLabel?.font = .systemFont(ofSize: 16, weight: .semibold)
        closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
        view.addSubview(closeButton)

        overlayCard.translatesAutoresizingMaskIntoConstraints = false
        overlayCard.backgroundColor = UIColor(white: 0.08, alpha: 0.82)
        overlayCard.layer.cornerRadius = 22
        overlayCard.layer.borderWidth = 1
        overlayCard.layer.borderColor = UIColor(red: 1.0, green: 0.82, blue: 0.4, alpha: 0.18).cgColor
        view.addSubview(overlayCard)

        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        titleLabel.textColor = UIColor(red: 0.98, green: 0.94, blue: 0.89, alpha: 1.0)
        titleLabel.font = .systemFont(ofSize: 28, weight: .bold)
        titleLabel.numberOfLines = 0
        overlayCard.addSubview(titleLabel)

        bodyLabel.translatesAutoresizingMaskIntoConstraints = false
        bodyLabel.textColor = UIColor(red: 0.82, green: 0.74, blue: 0.66, alpha: 1.0)
        bodyLabel.font = .systemFont(ofSize: 16, weight: .medium)
        bodyLabel.numberOfLines = 0
        overlayCard.addSubview(bodyLabel)

        activityIndicator.translatesAutoresizingMaskIntoConstraints = false
        activityIndicator.color = UIColor(red: 1.0, green: 0.74, blue: 0.25, alpha: 1.0)
        overlayCard.addSubview(activityIndicator)

        primaryButton.translatesAutoresizingMaskIntoConstraints = false
        primaryButton.isHidden = true
        primaryButton.backgroundColor = UIColor(red: 1.0, green: 0.74, blue: 0.25, alpha: 1.0)
        primaryButton.setTitleColor(.black, for: .normal)
        primaryButton.titleLabel?.font = .systemFont(ofSize: 17, weight: .bold)
        primaryButton.layer.cornerRadius = 18
        primaryButton.contentEdgeInsets = UIEdgeInsets(top: 14, left: 20, bottom: 14, right: 20)
        primaryButton.addTarget(self, action: #selector(primaryTapped), for: .touchUpInside)
        overlayCard.addSubview(primaryButton)

        secondaryButton.translatesAutoresizingMaskIntoConstraints = false
        secondaryButton.isHidden = true
        secondaryButton.backgroundColor = UIColor(white: 1.0, alpha: 0.05)
        secondaryButton.setTitleColor(UIColor(red: 0.98, green: 0.94, blue: 0.89, alpha: 1.0), for: .normal)
        secondaryButton.titleLabel?.font = .systemFont(ofSize: 16, weight: .semibold)
        secondaryButton.layer.cornerRadius = 18
        secondaryButton.layer.borderWidth = 1
        secondaryButton.layer.borderColor = UIColor(white: 1.0, alpha: 0.08).cgColor
        secondaryButton.contentEdgeInsets = UIEdgeInsets(top: 14, left: 20, bottom: 14, right: 20)
        secondaryButton.addTarget(self, action: #selector(secondaryTapped), for: .touchUpInside)
        overlayCard.addSubview(secondaryButton)

        NSLayoutConstraint.activate([
            previewView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            previewView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            previewView.topAnchor.constraint(equalTo: view.topAnchor),
            previewView.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            closeButton.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12),
            closeButton.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20),

            overlayCard.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 20),
            overlayCard.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20),
            overlayCard.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -24),

            titleLabel.leadingAnchor.constraint(equalTo: overlayCard.leadingAnchor, constant: 20),
            titleLabel.trailingAnchor.constraint(equalTo: overlayCard.trailingAnchor, constant: -20),
            titleLabel.topAnchor.constraint(equalTo: overlayCard.topAnchor, constant: 20),

            bodyLabel.leadingAnchor.constraint(equalTo: overlayCard.leadingAnchor, constant: 20),
            bodyLabel.trailingAnchor.constraint(equalTo: overlayCard.trailingAnchor, constant: -20),
            bodyLabel.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 10),

            activityIndicator.leadingAnchor.constraint(equalTo: overlayCard.leadingAnchor, constant: 20),
            activityIndicator.topAnchor.constraint(equalTo: bodyLabel.bottomAnchor, constant: 18),
            activityIndicator.bottomAnchor.constraint(equalTo: overlayCard.bottomAnchor, constant: -20),

            primaryButton.leadingAnchor.constraint(equalTo: overlayCard.leadingAnchor, constant: 20),
            primaryButton.trailingAnchor.constraint(equalTo: overlayCard.trailingAnchor, constant: -20),
            primaryButton.topAnchor.constraint(equalTo: bodyLabel.bottomAnchor, constant: 20),

            secondaryButton.leadingAnchor.constraint(equalTo: overlayCard.leadingAnchor, constant: 20),
            secondaryButton.trailingAnchor.constraint(equalTo: overlayCard.trailingAnchor, constant: -20),
            secondaryButton.topAnchor.constraint(equalTo: primaryButton.bottomAnchor, constant: 12),
            secondaryButton.bottomAnchor.constraint(equalTo: overlayCard.bottomAnchor, constant: -20)
        ])

        resetLiveness()
        applyCurrentLivenessPrompt()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        startSessionIfNeeded()
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        stopSession()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        previewView.layer.sublayers?
            .compactMap { $0 as? AVCaptureVideoPreviewLayer }
            .first?
            .frame = previewView.bounds
    }

    private func startSessionIfNeeded() {
        sessionQueue.async {
            do {
                if !self.didConfigureSession {
                    try self.configureSession()
                    self.didConfigureSession = true
                }
                guard !self.session.isRunning else { return }
                self.session.startRunning()
            } catch CameraScanRuntimeError.unavailable {
                self.finish(
                    CameraScanCoordinator.ScanResult(
                        scanAvailable: false,
                        faceCount: 0,
                        verificationReady: false,
                        qualityStatus: nil,
                        errorStatus: "camera_unavailable"
                    )
                )
            } catch CameraScanRuntimeError.busy {
                self.finish(
                    CameraScanCoordinator.ScanResult(
                        scanAvailable: false,
                        faceCount: 0,
                        verificationReady: false,
                        qualityStatus: nil,
                        errorStatus: "camera_busy"
                    )
                )
            } catch {
                self.finish(
                    CameraScanCoordinator.ScanResult(
                        scanAvailable: false,
                        faceCount: 0,
                        verificationReady: false,
                        qualityStatus: nil,
                        errorStatus: "capture_failed"
                    )
                )
            }
        }
    }

    private func configureSession() throws {
        session.beginConfiguration()
        session.sessionPreset = .high

        defer { session.commitConfiguration() }

        session.inputs.forEach { session.removeInput($0) }
        session.outputs.forEach { session.removeOutput($0) }

        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front) else {
            throw CameraScanRuntimeError.unavailable
        }

        let input: AVCaptureDeviceInput
        do {
            input = try AVCaptureDeviceInput(device: device)
        } catch let error as NSError {
            if error.domain == AVFoundationErrorDomain,
               error.code == AVError.deviceAlreadyUsedByAnotherSession.rawValue {
                throw CameraScanRuntimeError.busy
            }
            throw CameraScanRuntimeError.unavailable
        }

        guard session.canAddInput(input) else {
            throw CameraScanRuntimeError.unavailable
        }
        session.addInput(input)

        videoOutput.alwaysDiscardsLateVideoFrames = true
        videoOutput.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        videoOutput.setSampleBufferDelegate(self, queue: sessionQueue)
        guard session.canAddOutput(videoOutput) else {
            throw CameraScanRuntimeError.unavailable
        }
        session.addOutput(videoOutput)

        guard session.canAddOutput(metadataOutput) else {
            throw CameraScanRuntimeError.unavailable
        }
        session.addOutput(metadataOutput)
        metadataOutput.setMetadataObjectsDelegate(self, queue: sessionQueue)
        metadataOutput.metadataObjectTypes = metadataOutput.availableMetadataObjectTypes.contains(.face) ? [.face] : []

        if let videoConnection = videoOutput.connection(with: .video), videoConnection.isVideoOrientationSupported {
            videoConnection.videoOrientation = .portrait
        }
        if let metadataConnection = metadataOutput.connection(with: .video), metadataConnection.isVideoOrientationSupported {
            metadataConnection.videoOrientation = .portrait
        }

        DispatchQueue.main.async {
            let previewLayer = AVCaptureVideoPreviewLayer(session: self.session)
            previewLayer.videoGravity = .resizeAspectFill
            previewLayer.frame = self.previewView.bounds
            self.previewView.layer.sublayers?.forEach { $0.removeFromSuperlayer() }
            self.previewView.layer.addSublayer(previewLayer)
        }
    }

    func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        guard !didFinish else { return }
        latestSampleBuffer = sampleBuffer
    }

    func metadataOutput(
        _ output: AVCaptureMetadataOutput,
        didOutput metadataObjects: [AVMetadataObject],
        from connection: AVCaptureConnection
    ) {
        guard !didFinish, phase == .scanning, !captureScheduled else { return }

        let faces = metadataObjects.compactMap { $0 as? AVMetadataFaceObject }
        if faces.count > 1 {
            stableFrames = 0
            DispatchQueue.main.async {
                self.applyLiveFeedback(title: "Mehrere Gesichter", body: "Bitte bleib allein im Bild. Der Liveness-Scan prueft nur genau eine Person.")
            }
            return
        }

        guard let face = faces.first else {
            stableFrames = 0
            DispatchQueue.main.async {
                self.applyLiveFeedback(title: "Gesicht ausrichten", body: "Halte dein Gesicht klar vor die Frontkamera. Erst dann startet der Liveness-Scan.")
            }
            return
        }

        let yawAngle = face.hasYawAngle ? face.yawAngle : 0
        evaluateLiveness(using: yawAngle)
    }

    private func evaluateLiveness(using yawAngle: CGFloat) {
        let straightSatisfied = abs(yawAngle) <= 12
        let leftSatisfied = yawAngle <= -18
        let rightSatisfied = yawAngle >= 18

        switch currentLivenessStep {
        case .straight:
            DispatchQueue.main.async {
                self.applyLiveFeedback(
                    title: "Geradeaus schauen",
                    body: straightSatisfied
                        ? "Geradeaus erkannt. Gleich folgt die seitliche Bewegung fuer den echten Liveness-Scan."
                        : "Blick kurz geradeaus in die Kamera halten. Erst danach geht der Scan weiter."
                )
            }
            registerStepProgress(satisfied: straightSatisfied) { [weak self] in
                self?.currentLivenessStep = .left
                self?.applyCurrentLivenessPrompt()
            }
        case .left:
            DispatchQueue.main.async {
                self.applyLiveFeedback(
                    title: "Nach links schauen",
                    body: leftSatisfied
                        ? "Linke Bewegung erkannt. Als Naechstes bitte nach rechts schauen."
                        : "Dreh deinen Kopf leicht nach links. Diese Bewegung wird echt im Live-Stream geprueft."
                )
            }
            registerStepProgress(satisfied: leftSatisfied) { [weak self] in
                self?.currentLivenessStep = .right
                self?.applyCurrentLivenessPrompt()
            }
        case .right:
            DispatchQueue.main.async {
                self.applyLiveFeedback(
                    title: "Nach rechts schauen",
                    body: rightSatisfied
                        ? "Rechte Bewegung erkannt. Der Verifizierungs-Scan wird jetzt mit einem echten Frame abgeschlossen."
                        : "Dreh deinen Kopf jetzt leicht nach rechts. Danach wird der finale Verifizierungsframe geprueft."
                )
            }
            registerStepProgress(satisfied: rightSatisfied) { [weak self] in
                self?.currentLivenessStep = .complete
                self?.beginFinalVerification()
            }
        case .complete:
            break
        }
    }

    private func registerStepProgress(satisfied: Bool, completion: @escaping () -> Void) {
        stableFrames = satisfied ? (stableFrames + 1) : 0
        guard stableFrames >= stableFrameThreshold else { return }
        stableFrames = 0
        completion()
    }

    private func beginFinalVerification() {
        guard !captureScheduled else { return }
        captureScheduled = true
        DispatchQueue.main.async {
            self.titleLabel.text = "Scan läuft"
            self.bodyLabel.text = "Geradeaus, links und rechts wurden erkannt. Vision prueft jetzt den finalen Verifizierungsframe."
            self.activityIndicator.isHidden = false
            self.activityIndicator.startAnimating()
            self.primaryButton.isHidden = true
            self.secondaryButton.isHidden = true
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { [weak self] in
            self?.captureCurrentFrame()
        }
    }

    private func captureCurrentFrame() {
        sessionQueue.async {
            guard !self.didFinish else { return }
            guard let sampleBuffer = self.latestSampleBuffer else {
                self.finish(
                    CameraScanCoordinator.ScanResult(
                        scanAvailable: false,
                        faceCount: 0,
                        verificationReady: false,
                        qualityStatus: nil,
                        errorStatus: "capture_failed"
                    )
                )
                return
            }

            let request = VNDetectFaceRectanglesRequest()

            do {
                let handler = VNImageRequestHandler(
                    cmSampleBuffer: sampleBuffer,
                    orientation: .leftMirrored,
                    options: [:]
                )
                try handler.perform([request])
                let faces = request.results ?? []
                let result = self.buildResult(from: faces)
                self.handleScanResult(result)
            } catch {
                self.finish(
                    CameraScanCoordinator.ScanResult(
                        scanAvailable: true,
                        faceCount: 0,
                        verificationReady: false,
                        qualityStatus: nil,
                        errorStatus: "vision_failed"
                    )
                )
            }
        }
    }

    private func handleScanResult(_ result: CameraScanCoordinator.ScanResult) {
        if result.errorStatus == nil, result.verificationReady, result.faceCount == 1 {
            DispatchQueue.main.async {
                self.applySuccessState()
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
                self.finish(result)
            }
            return
        }

        if result.errorStatus == "no_face" || result.errorStatus == "multiple_faces" {
            DispatchQueue.main.async {
                self.applyRetryState(for: result)
            }
            return
        }

        finish(result)
    }

    private func buildResult(from faces: [VNFaceObservation]) -> CameraScanCoordinator.ScanResult {
        if faces.isEmpty {
            return CameraScanCoordinator.ScanResult(
                scanAvailable: true,
                faceCount: 0,
                verificationReady: false,
                qualityStatus: nil,
                errorStatus: "no_face"
            )
        }

        if faces.count > 1 {
            return CameraScanCoordinator.ScanResult(
                scanAvailable: true,
                faceCount: faces.count,
                verificationReady: false,
                qualityStatus: nil,
                errorStatus: "multiple_faces"
            )
        }

        return CameraScanCoordinator.ScanResult(
            scanAvailable: true,
            faceCount: 1,
            verificationReady: currentLivenessStep == .complete,
            qualityStatus: currentLivenessStep == .complete ? "liveness_complete" : nil,
            errorStatus: currentLivenessStep == .complete ? nil : "capture_failed"
        )
    }

    private func stopSession() {
        sessionQueue.async {
            if self.session.isRunning {
                self.session.stopRunning()
            }
        }
    }

    @objc
    private func primaryTapped() {
        if phase == .result {
            restartScan()
        }
    }

    @objc
    private func secondaryTapped() {
        finish(
            CameraScanCoordinator.ScanResult(
                scanAvailable: false,
                faceCount: 0,
                verificationReady: false,
                qualityStatus: nil,
                errorStatus: "capture_failed"
            )
        )
    }

    @objc
    private func closeTapped() {
        finish(
            CameraScanCoordinator.ScanResult(
                scanAvailable: false,
                faceCount: 0,
                verificationReady: false,
                qualityStatus: nil,
                errorStatus: "capture_failed"
            )
        )
    }

    private func restartScan() {
        phase = .scanning
        captureScheduled = false
        latestSampleBuffer = nil
        resetLiveness()
        applyCurrentLivenessPrompt()
    }

    private func resetLiveness() {
        currentLivenessStep = .straight
        stableFrames = 0
        phase = .scanning
    }

    private func applyCurrentLivenessPrompt() {
        switch currentLivenessStep {
        case .straight:
            applyLiveFeedback(title: "Geradeaus schauen", body: "Halte dein Gesicht ruhig und schau kurz geradeaus in die Kamera. Danach fuehrt der echte Liveness-Scan weiter.")
        case .left:
            applyLiveFeedback(title: "Nach links schauen", body: "Der Geradeaus-Blick wurde erkannt. Dreh deinen Kopf jetzt leicht nach links.")
        case .right:
            applyLiveFeedback(title: "Nach rechts schauen", body: "Die linke Bewegung wurde erkannt. Dreh deinen Kopf jetzt leicht nach rechts.")
        case .complete:
            titleLabel.text = "Scan läuft"
            bodyLabel.text = "Die Liveness-Schritte sind durchlaufen. Der Verifizierungsframe wird jetzt ausgewertet."
        }
    }

    private func applyLiveFeedback(title: String, body: String) {
        titleLabel.text = title
        bodyLabel.text = body
        activityIndicator.isHidden = false
        activityIndicator.startAnimating()
        primaryButton.isHidden = true
        secondaryButton.isHidden = true
    }

    private func applySuccessState() {
        phase = .result
        titleLabel.text = "Verifizierung erfolgreich"
        bodyLabel.text = "Geradeaus, links und rechts wurden erkannt. Genau ein Gesicht blieb danach im Verifizierungsframe sichtbar."
        activityIndicator.stopAnimating()
        activityIndicator.isHidden = true
        primaryButton.isHidden = true
        secondaryButton.isHidden = true
    }

    private func applyRetryState(for result: CameraScanCoordinator.ScanResult) {
        phase = .result
        titleLabel.text = result.errorStatus == "multiple_faces" ? "Mehrere Gesichter erkannt" : "Kein Gesicht erkannt"
        bodyLabel.text = result.errorStatus == "multiple_faces"
            ? "Im finalen Verifizierungsframe waren mehrere Gesichter sichtbar. Bitte starte den Liveness-Scan erneut alleine."
            : "Im finalen Verifizierungsframe war kein Gesicht klar genug sichtbar. Bitte fuehre den Liveness-Scan erneut durch."
        activityIndicator.stopAnimating()
        activityIndicator.isHidden = true
        primaryButton.setTitle("Erneut scannen", for: .normal)
        primaryButton.isHidden = false
        secondaryButton.setTitle("Abbrechen", for: .normal)
        secondaryButton.isHidden = false
    }

    private func finish(_ result: CameraScanCoordinator.ScanResult) {
        guard !didFinish else { return }
        didFinish = true
        stopSession()

        DispatchQueue.main.async {
            self.dismiss(animated: true) {
                self.completion(result)
            }
        }
    }
}

private enum CameraScanRuntimeError: Error {
    case unavailable
    case busy
}
