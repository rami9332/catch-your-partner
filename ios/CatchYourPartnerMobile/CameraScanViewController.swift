import AVFoundation
import ImageIO
import UIKit
import Vision

final class CameraScanViewController: UIViewController, AVCaptureVideoDataOutputSampleBufferDelegate {
    private enum ScanPhase {
        case scanning
        case result
    }

    private let session = AVCaptureSession()
    private let sessionQueue = DispatchQueue(label: "com.catchyourpartner.camera-scan.session")
    private let videoOutput = AVCaptureVideoDataOutput()
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
        titleLabel.text = "Gesicht wird erfasst"
        titleLabel.textColor = UIColor(red: 0.98, green: 0.94, blue: 0.89, alpha: 1.0)
        titleLabel.font = .systemFont(ofSize: 28, weight: .bold)
        titleLabel.numberOfLines = 0
        overlayCard.addSubview(titleLabel)

        bodyLabel.translatesAutoresizingMaskIntoConstraints = false
        bodyLabel.text = "Die Frontkamera laeuft nativ. Danach prueft Vision den erfassten Frame auf echte Gesichter."
        bodyLabel.textColor = UIColor(red: 0.82, green: 0.74, blue: 0.66, alpha: 1.0)
        bodyLabel.font = .systemFont(ofSize: 16, weight: .medium)
        bodyLabel.numberOfLines = 0
        overlayCard.addSubview(bodyLabel)

        activityIndicator.translatesAutoresizingMaskIntoConstraints = false
        activityIndicator.color = UIColor(red: 1.0, green: 0.74, blue: 0.25, alpha: 1.0)
        activityIndicator.startAnimating()
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

        applyScanningState()
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

        if let connection = videoOutput.connection(with: .video), connection.isVideoOrientationSupported {
            connection.videoOrientation = .portrait
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

        guard !captureScheduled else { return }
        captureScheduled = true

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.85) { [weak self] in
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
                let faces = (request.results as? [VNFaceObservation]) ?? []
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
            verificationReady: true,
            qualityStatus: "ok",
            errorStatus: nil
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
        applyScanningState()
    }

    private func applyScanningState() {
        titleLabel.text = "Gesicht wird erfasst"
        bodyLabel.text = "Halte dein Gesicht ruhig in die Frontkamera. Vision prueft danach den naechsten echten Frame."
        activityIndicator.isHidden = false
        activityIndicator.startAnimating()
        primaryButton.isHidden = true
        secondaryButton.isHidden = true
    }

    private func applySuccessState() {
        phase = .result
        titleLabel.text = "Gesicht erkannt"
        bodyLabel.text = "Ein einzelnes Gesicht wurde sauber erkannt. Die Verifizierung wird jetzt vorbereitet."
        activityIndicator.stopAnimating()
        activityIndicator.isHidden = true
        primaryButton.isHidden = true
        secondaryButton.isHidden = true
    }

    private func applyRetryState(for result: CameraScanCoordinator.ScanResult) {
        phase = .result
        titleLabel.text = result.errorStatus == "multiple_faces" ? "Mehrere Gesichter erkannt" : "Kein Gesicht erkannt"
        bodyLabel.text = result.errorStatus == "multiple_faces"
            ? "Bitte richte die Kamera so aus, dass nur eine Person im Bild ist."
            : "Bitte halte dein Gesicht klar in die Kamera und versuche es noch einmal."
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
