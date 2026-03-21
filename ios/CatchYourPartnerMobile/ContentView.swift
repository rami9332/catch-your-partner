import SwiftUI

struct ContentView: View {
    @AppStorage("demoHost") private var demoHost = ""
    @State private var hostInput = ""
    private let webVersion = "20260320-2"

    private var bundledAppURL: URL? {
        Bundle.main.url(forResource: "index", withExtension: "html")
    }

    private var normalizedHost: String {
        let raw = hostInput.trimmingCharacters(in: .whitespacesAndNewlines)
        if raw.isEmpty { return "" }
        if raw.hasPrefix("http://") || raw.hasPrefix("https://") {
            return raw
        }
        return "http://\(raw)"
    }

    private var appURL: URL? {
        guard !demoHost.isEmpty else { return nil }
        let trimmed = demoHost.trimmingCharacters(in: .whitespacesAndNewlines)

        if let bundledAppURL {
            var components = URLComponents(url: bundledAppURL, resolvingAgainstBaseURL: false)
            components?.queryItems = [URLQueryItem(name: "v", value: webVersion)]
            return components?.url ?? bundledAppURL
        }

        return URL(string: "\(trimmed):3000/index.html?v=\(webVersion)")
    }

    private var backendOrigin: String? {
        guard !demoHost.isEmpty else { return nil }
        let trimmed = demoHost.trimmingCharacters(in: .whitespacesAndNewlines)
        return "\(trimmed):8000"
    }

    private var showsHostBadge: Bool {
        guard let appURL else { return false }
        guard !appURL.isFileURL else { return false }
        return appURL.query?.contains("debug=1") == true || appURL.path.hasSuffix("/admin")
    }

    var body: some View {
        NavigationStack {
            Group {
                if let appURL {
                    DemoWebView(url: appURL, backendOrigin: backendOrigin)
                        .overlay(alignment: .topTrailing) {
                            if showsHostBadge {
                                Button("Host") {
                                    demoHost = ""
                                    hostInput = ""
                                }
                                .font(.caption.weight(.semibold))
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)
                                .background(.ultraThinMaterial, in: Capsule())
                                .padding()
                            }
                        }
                } else {
                    setupView
                }
            }
            .navigationBarHidden(true)
        }
        .onAppear {
            if hostInput.isEmpty {
                hostInput = demoHost.replacingOccurrences(of: "http://", with: "")
                    .replacingOccurrences(of: "https://", with: "")
            }
        }
    }

    private var setupView: some View {
        ZStack {
            LinearGradient(
                colors: [Color(red: 0.06, green: 0.11, blue: 0.19), Color(red: 0.13, green: 0.26, blue: 0.24)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            VStack(alignment: .leading, spacing: 20) {
                Text("Catch Your Partner")
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)

                Text("Gib einmal die lokale IP deines Macs ein. Danach startet die App auf deinem iPhone direkt in der sauberen App-Ansicht.")
                    .font(.body)
                    .foregroundStyle(.white.opacity(0.8))

                VStack(alignment: .leading, spacing: 10) {
                    Text("Mac-IP oder Host")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.75))
                    TextField("192.168.x.x", text: $hostInput)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .padding()
                        .background(Color.white.opacity(0.1), in: RoundedRectangle(cornerRadius: 16))
                        .foregroundStyle(.white)
                }

                Button {
                    demoHost = normalizedHost
                } label: {
                    Text("App öffnen")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.orange, in: RoundedRectangle(cornerRadius: 18))
                        .foregroundStyle(Color.black)
                }
                .disabled(normalizedHost.isEmpty)
                .opacity(normalizedHost.isEmpty ? 0.5 : 1)

                VStack(alignment: .leading, spacing: 8) {
                    Text("Vorher auf deinem Mac starten:")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.75))
                    Text("1. docker compose up -d\n2. python3 -m http.server 3000")
                        .font(.caption.monospaced())
                        .foregroundStyle(.white.opacity(0.85))
                }

                Spacer()
            }
            .padding(24)
        }
    }
}
