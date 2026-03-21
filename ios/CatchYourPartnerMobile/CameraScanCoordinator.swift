import AVFoundation
import Foundation
import UIKit

final class CameraScanCoordinator {
    struct ScanResult {
        let type = "cameraScanResult"
        let scanAvailable: Bool
        let faceCount: Int
        let verificationReady: Bool
        let qualityStatus: String?
        let errorStatus: String?

        var jsonString: String {
            let quality = qualityStatus.map { "\"\($0)\"" } ?? "null"
            let error = errorStatus.map { "\"\($0)\"" } ?? "null"
            return """
            {"type":"\(type)","scanAvailable":\(scanAvailable ? "true" : "false"),"faceCount":\(faceCount),"verificationReady":\(verificationReady ? "true" : "false"),"qualityStatus":\(quality),"errorStatus":\(error)}
            """
        }
    }

    private var isPresenting = false

    func startScan(completion: @escaping (ScanResult) -> Void) {
        let currentStatus = AVCaptureDevice.authorizationStatus(for: .video)
        switch currentStatus {
        case .authorized:
            presentScanFlow(completion: completion)
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { granted in
                if granted {
                    self.presentScanFlow(completion: completion)
                } else {
                    completion(
                        ScanResult(
                            scanAvailable: false,
                            faceCount: 0,
                            verificationReady: false,
                            qualityStatus: nil,
                            errorStatus: "camera_denied"
                        )
                    )
                }
            }
        case .denied, .restricted:
            completion(
                ScanResult(
                    scanAvailable: false,
                    faceCount: 0,
                    verificationReady: false,
                    qualityStatus: nil,
                    errorStatus: "camera_denied"
                )
            )
        @unknown default:
            completion(
                ScanResult(
                    scanAvailable: false,
                    faceCount: 0,
                    verificationReady: false,
                    qualityStatus: nil,
                    errorStatus: "camera_unavailable"
                )
            )
        }
    }

    private func presentScanFlow(completion: @escaping (ScanResult) -> Void) {
        DispatchQueue.main.async {
            guard !self.isPresenting else {
                completion(
                    ScanResult(
                        scanAvailable: false,
                        faceCount: 0,
                        verificationReady: false,
                        qualityStatus: nil,
                        errorStatus: "camera_busy"
                    )
                )
                return
            }

            guard let presenter = Self.topViewController() else {
                completion(
                    ScanResult(
                        scanAvailable: false,
                        faceCount: 0,
                        verificationReady: false,
                        qualityStatus: nil,
                        errorStatus: "camera_unavailable"
                    )
                )
                return
            }

            self.isPresenting = true
            let controller = CameraScanViewController { [weak self] result in
                self?.isPresenting = false
                completion(result)
            }
            controller.modalPresentationStyle = .fullScreen
            presenter.present(controller, animated: true)
        }
    }

    private static func topViewController(
        base: UIViewController? = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap(\.windows)
            .first(where: \.isKeyWindow)?
            .rootViewController
    ) -> UIViewController? {
        if let navigation = base as? UINavigationController {
            return topViewController(base: navigation.visibleViewController)
        }
        if let tab = base as? UITabBarController {
            return topViewController(base: tab.selectedViewController)
        }
        if let presented = base?.presentedViewController {
            return topViewController(base: presented)
        }
        return base
    }
}
