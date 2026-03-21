import SwiftUI
import WebKit

struct DemoWebView: UIViewRepresentable {
    let url: URL
    let backendOrigin: String?

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    private func request(for url: URL) -> URLRequest {
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        return request
    }

    private func load(_ url: URL, in webView: WKWebView) {
        if url.isFileURL {
            webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
            return
        }
        webView.load(request(for: url))
    }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.allowsInlineMediaPlayback = true
        let controller = WKUserContentController()
        if let backendOrigin, !backendOrigin.isEmpty {
            let escapedOrigin = backendOrigin
                .replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "'", with: "\\'")
            let scriptSource = """
            window.__CYP_BACKEND__ = '\(escapedOrigin)';
            try { localStorage.setItem('catchyourpartner.backendOrigin', '\(escapedOrigin)'); } catch (e) {}
            window.CYPNative = window.CYPNative || {};
            window.CYPNative.startCameraScan = function () {
              if (!window.webkit || !window.webkit.messageHandlers || !window.webkit.messageHandlers.nativeBridge) return false;
              window.webkit.messageHandlers.nativeBridge.postMessage({ action: 'startCameraScan' });
              return true;
            };
            window.CYPNative.openMeetingMap = function () {
              if (!window.webkit || !window.webkit.messageHandlers || !window.webkit.messageHandlers.nativeBridge) return false;
              var payload = { action: 'openMeetingMap' };
              if (arguments.length && arguments[0] && typeof arguments[0] === 'object') {
                if (arguments[0].meetingPoint) payload.meetingPoint = arguments[0].meetingPoint;
                if (arguments[0].candidateLocation) payload.candidateLocation = arguments[0].candidateLocation;
                if (arguments[0].acceptance) payload.acceptance = arguments[0].acceptance;
                if (arguments[0].arrival) payload.arrival = arguments[0].arrival;
                if (arguments[0].ok) payload.ok = arguments[0].ok;
                if (arguments[0].meetingContext) payload.meetingContext = arguments[0].meetingContext;
                if (!arguments[0].meetingPoint && !arguments[0].candidateLocation) payload.meetingPoint = arguments[0];
              }
              window.webkit.messageHandlers.nativeBridge.postMessage(payload);
              return true;
            };
            """
            let script = WKUserScript(source: scriptSource, injectionTime: .atDocumentStart, forMainFrameOnly: true)
            controller.addUserScript(script)
        }
        controller.add(context.coordinator, name: "nativeBridge")
        configuration.userContentController = controller
        let webView = WKWebView(frame: .zero, configuration: configuration)
        context.coordinator.webView = webView
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.allowsBackForwardNavigationGestures = true
        load(url, in: webView)
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        guard webView.url != url else { return }
        load(url, in: webView)
    }

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
        weak var webView: WKWebView?
        private let cameraScanCoordinator = CameraScanCoordinator()
        private let mapMeetingCoordinator = MapMeetingCoordinator()

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            guard message.name == "nativeBridge" else { return }
            guard let payload = message.body as? [String: Any], let action = payload["action"] as? String else { return }

            if action == "startCameraScan" {
                cameraScanCoordinator.startScan { [weak self] result in
                    self?.sendCameraScanResultToWeb(result)
                }
            } else if action == "openMeetingMap" {
                let meetingPoint = Self.parseMeetingPoint(from: payload["meetingPoint"] as? [String: Any])
                let candidateLocation = Self.parseCandidateLocation(from: payload["candidateLocation"] as? [String: Any])
                let acceptanceStatus = Self.parseAcceptanceStatus(from: payload["acceptance"] as? [String: Any])
                let arrivalStatus = Self.parseArrivalStatus(from: payload["arrival"] as? [String: Any])
                let okStatus = Self.parseOkStatus(from: payload["ok"] as? [String: Any])
                let meetingContext = Self.parseMeetingActionContext(from: payload["meetingContext"] as? [String: Any])
                mapMeetingCoordinator.openMap(meetingPoint: meetingPoint, candidateLocation: candidateLocation, acceptanceStatus: acceptanceStatus, arrivalStatus: arrivalStatus, okStatus: okStatus, meetingContext: meetingContext) { [weak self] result in
                    self?.sendMeetingMapResultToWeb(result)
                }
            }
        }

        private static func parseMeetingPoint(from payload: [String: Any]?) -> MapMeetingCoordinator.MeetingPoint? {
            guard let payload,
                  let name = payload["name"] as? String,
                  let latitude = payload["latitude"] as? Double ?? payload["lat"] as? Double,
                  let longitude = payload["longitude"] as? Double ?? payload["lng"] as? Double
            else {
                return nil
            }

            return MapMeetingCoordinator.MeetingPoint(name: name, latitude: latitude, longitude: longitude)
        }

        private static func parseCandidateLocation(from payload: [String: Any]?) -> MapMeetingCoordinator.CandidateLocation? {
            guard let payload,
                  let latitude = payload["latitude"] as? Double ?? payload["lat"] as? Double,
                  let longitude = payload["longitude"] as? Double ?? payload["lng"] as? Double
            else {
                return nil
            }

            return MapMeetingCoordinator.CandidateLocation(latitude: latitude, longitude: longitude)
        }

        private static func parseAcceptanceStatus(from payload: [String: Any]?) -> MapMeetingCoordinator.AcceptanceStatus? {
            guard let payload else { return nil }
            let youAccepted = payload["youAccepted"] as? Bool ?? false
            let otherAccepted = payload["otherAccepted"] as? Bool ?? false
            let fullyAccepted = payload["fullyAccepted"] as? Bool ?? false
            return MapMeetingCoordinator.AcceptanceStatus(
                youAccepted: youAccepted,
                otherAccepted: otherAccepted,
                fullyAccepted: fullyAccepted
            )
        }

        private static func parseArrivalStatus(from payload: [String: Any]?) -> MapMeetingCoordinator.ArrivalStatus? {
            guard let payload else { return nil }
            let youArrived = payload["youArrived"] as? Bool ?? false
            let otherArrived = payload["otherArrived"] as? Bool ?? false
            let bothArrived = payload["bothArrived"] as? Bool ?? false
            return MapMeetingCoordinator.ArrivalStatus(
                youArrived: youArrived,
                otherArrived: otherArrived,
                bothArrived: bothArrived
            )
        }

        private static func parseMeetingActionContext(from payload: [String: Any]?) -> MapMeetingCoordinator.MeetingActionContext? {
            guard let payload,
                  let meetingId = payload["meetingId"] as? Int ?? Int(payload["meetingId"] as? String ?? ""),
                  let backendOrigin = payload["backendOrigin"] as? String,
                  let authToken = payload["authToken"] as? String,
                  !backendOrigin.isEmpty,
                  !authToken.isEmpty
            else {
                return nil
            }

            return MapMeetingCoordinator.MeetingActionContext(
                meetingId: meetingId,
                backendOrigin: backendOrigin,
                authToken: authToken
            )
        }

        private static func parseOkStatus(from payload: [String: Any]?) -> MapMeetingCoordinator.OkStatus? {
            guard let payload else { return nil }
            let youOk = payload["youOk"] as? Bool ?? false
            let otherOk = payload["otherOk"] as? Bool ?? false
            let bothOk = payload["bothOk"] as? Bool ?? false
            let chatUnlocked = payload["chatUnlocked"] as? Bool ?? false
            return MapMeetingCoordinator.OkStatus(
                youOk: youOk,
                otherOk: otherOk,
                bothOk: bothOk,
                chatUnlocked: chatUnlocked
            )
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            showError(in: webView, error: error)
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            showError(in: webView, error: error)
        }

        @available(iOS 15.0, *)
        func webView(
            _ webView: WKWebView,
            requestMediaCapturePermissionFor origin: WKSecurityOrigin,
            initiatedByFrame frame: WKFrameInfo,
            type: WKMediaCaptureType,
            decisionHandler: @escaping (WKPermissionDecision) -> Void
        ) {
            decisionHandler(.grant)
        }

        private func sendCameraScanResultToWeb(_ result: CameraScanCoordinator.ScanResult) {
            DispatchQueue.main.async { [weak self] in
                guard let webView = self?.webView else { return }
                let script = """
                window.dispatchEvent(new CustomEvent('cyp:native-camera-scan', { detail: \(result.jsonString) }));
                """
                webView.evaluateJavaScript(script, completionHandler: nil)
            }
        }

        private func sendMeetingMapResultToWeb(_ result: MapMeetingCoordinator.MapResult) {
            DispatchQueue.main.async { [weak self] in
                guard let webView = self?.webView else { return }
                let script = """
                window.dispatchEvent(new CustomEvent('cyp:native-meeting-map', { detail: \(result.jsonString) }));
                """
                webView.evaluateJavaScript(script, completionHandler: nil)
            }
        }

        private func showError(in webView: WKWebView, error: Error) {
            let message = (error as NSError).localizedDescription
                .replacingOccurrences(of: "&", with: "&amp;")
                .replacingOccurrences(of: "<", with: "&lt;")
                .replacingOccurrences(of: ">", with: "&gt;")
            let failingURL = webView.url?.absoluteString ?? "Unbekannte URL"
            let safeURL = failingURL
                .replacingOccurrences(of: "&", with: "&amp;")
                .replacingOccurrences(of: "<", with: "&lt;")
                .replacingOccurrences(of: ">", with: "&gt;")

            let html = """
            <!DOCTYPE html>
            <html lang="de">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <style>
                :root { color-scheme: dark; }
                body {
                  margin: 0;
                  min-height: 100vh;
                  display: grid;
                  place-items: center;
                  padding: 24px;
                  background: #0d0d0d;
                  color: #f6efe3;
                  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                }
                .card {
                  width: min(100%, 420px);
                  padding: 24px;
                  border-radius: 24px;
                  background: linear-gradient(180deg, rgba(28, 28, 28, 0.96), rgba(18, 18, 18, 0.94));
                  border: 1px solid rgba(255, 209, 102, 0.12);
                  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
                }
                .eyebrow {
                  margin: 0 0 10px;
                  color: #ffd166;
                  font-size: 12px;
                  font-weight: 700;
                  letter-spacing: 0.14em;
                  text-transform: uppercase;
                }
                h1 {
                  margin: 0 0 12px;
                  font-size: 28px;
                  line-height: 1.05;
                }
                p {
                  margin: 0 0 12px;
                  color: #cdbda8;
                  line-height: 1.5;
                }
                code {
                  display: block;
                  padding: 12px 14px;
                  border-radius: 16px;
                  background: rgba(255, 255, 255, 0.04);
                  color: #f6efe3;
                  word-break: break-word;
                  font-size: 13px;
                }
              </style>
            </head>
            <body>
              <div class="card">
                <p class="eyebrow">WebView Hinweis</p>
                <h1>Die lokale App-Seite konnte nicht geladen werden.</h1>
                <p>Bitte prüfe, ob dein iPhone im selben WLAN ist und der Frontend-Server auf deinem Mac läuft.</p>
                <p>Geladene URL:</p>
                <code>\(safeURL)</code>
                <p>Fehlermeldung:</p>
                <code>\(message)</code>
              </div>
            </body>
            </html>
            """

            webView.loadHTMLString(html, baseURL: nil)
        }
    }
}
