import CoreLocation
import Foundation
import MapKit
import UIKit

final class MapMeetingViewController: UIViewController, CLLocationManagerDelegate, MKMapViewDelegate {
    private enum FlowState: Equatable {
        case locating
        case acceptanceWaitingYou
        case acceptanceWaitingOther
        case acceptanceReady
        case meetingPointReady
        case navigationActive
        case arrivalWaitingYou
        case arrivalWaitingOther
        case arrivalReady
        case okWaitingYou
        case okWaitingOther
        case okReady
        case chatUnlocked
        case error
    }

    private let mapView = MKMapView()
    private let overlayCard = UIView()
    private let statusChip = UILabel()
    private let titleLabel = UILabel()
    private let bodyLabel = UILabel()
    private let metricsStack = UIStackView()
    private let distanceLabel = UILabel()
    private let etaLabel = UILabel()
    private let primaryButton = UIButton(type: .system)
    private let closeButton = UIButton(type: .system)
    private let locationManager = CLLocationManager()

    private var latestLocation: CLLocation?
    private var didFinish = false
    private var meetingPointAnnotation: MKPointAnnotation?
    private var route: MKRoute?
    private var routeErrorStatus: String?
    private var directions: MKDirections?
    private var activeMeetingPoint: MapMeetingCoordinator.MeetingPoint?
    private let candidateLocation: MapMeetingCoordinator.CandidateLocation?
    private let meetingContext: MapMeetingCoordinator.MeetingActionContext?
    private var acceptanceStatus: MapMeetingCoordinator.AcceptanceStatus?
    private var arrivalStatus: MapMeetingCoordinator.ArrivalStatus?
    private var okStatus: MapMeetingCoordinator.OkStatus?
    private var latestServerMeeting: MapMeetingCoordinator.MapResult.ServerMeetingPayload?
    private var isResolvingMeetingPoint = false
    private var isSubmittingAction = false
    private var shouldOpenChatOnFinish = false
    private var flowState: FlowState = .locating
    private let completion: (MapMeetingCoordinator.MapResult) -> Void

    init(
        meetingPoint: MapMeetingCoordinator.MeetingPoint?,
        candidateLocation: MapMeetingCoordinator.CandidateLocation?,
        acceptanceStatus: MapMeetingCoordinator.AcceptanceStatus?,
        arrivalStatus: MapMeetingCoordinator.ArrivalStatus?,
        okStatus: MapMeetingCoordinator.OkStatus?,
        meetingContext: MapMeetingCoordinator.MeetingActionContext?,
        completion: @escaping (MapMeetingCoordinator.MapResult) -> Void
    ) {
        self.activeMeetingPoint = meetingPoint
        self.candidateLocation = candidateLocation
        self.acceptanceStatus = acceptanceStatus
        self.arrivalStatus = arrivalStatus
        self.okStatus = okStatus
        self.meetingContext = meetingContext
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

        mapView.translatesAutoresizingMaskIntoConstraints = false
        mapView.showsCompass = true
        mapView.showsScale = false
        mapView.pointOfInterestFilter = .includingAll
        mapView.delegate = self
        view.addSubview(mapView)

        closeButton.translatesAutoresizingMaskIntoConstraints = false
        closeButton.setTitle("Schliessen", for: .normal)
        closeButton.setTitleColor(.white, for: .normal)
        closeButton.titleLabel?.font = .systemFont(ofSize: 16, weight: .semibold)
        closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
        view.addSubview(closeButton)

        overlayCard.translatesAutoresizingMaskIntoConstraints = false
        overlayCard.backgroundColor = UIColor(white: 0.08, alpha: 0.82)
        overlayCard.layer.cornerRadius = 22
        overlayCard.layer.borderWidth = 1
        overlayCard.layer.borderColor = UIColor(red: 1.0, green: 0.82, blue: 0.4, alpha: 0.18).cgColor
        view.addSubview(overlayCard)

        statusChip.translatesAutoresizingMaskIntoConstraints = false
        statusChip.textColor = UIColor(red: 1.0, green: 0.82, blue: 0.4, alpha: 1.0)
        statusChip.font = .systemFont(ofSize: 12, weight: .bold)
        statusChip.textAlignment = .center
        statusChip.layer.cornerRadius = 11
        statusChip.layer.masksToBounds = true
        statusChip.backgroundColor = UIColor(red: 1.0, green: 0.82, blue: 0.4, alpha: 0.12)
        overlayCard.addSubview(statusChip)

        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        titleLabel.text = activeMeetingPoint == nil ? "Dein Standort" : "Treffpunkt auf der Karte"
        titleLabel.textColor = UIColor(red: 0.98, green: 0.94, blue: 0.89, alpha: 1.0)
        titleLabel.font = .systemFont(ofSize: 28, weight: .bold)
        titleLabel.numberOfLines = 0
        overlayCard.addSubview(titleLabel)

        bodyLabel.translatesAutoresizingMaskIntoConstraints = false
        bodyLabel.text = activeMeetingPoint == nil
            ? "MapKit oeffnet jetzt deinen echten Standort. Treffpunkt und Route folgen spaeter auf derselben nativen Basis."
            : "Dein Standort und der echte Treffpunkt werden nativ auf derselben Karte gezeigt."
        bodyLabel.textColor = UIColor(red: 0.82, green: 0.74, blue: 0.66, alpha: 1.0)
        bodyLabel.font = .systemFont(ofSize: 16, weight: .medium)
        bodyLabel.numberOfLines = 0
        overlayCard.addSubview(bodyLabel)

        metricsStack.translatesAutoresizingMaskIntoConstraints = false
        metricsStack.axis = .horizontal
        metricsStack.spacing = 12
        metricsStack.distribution = .fillEqually
        overlayCard.addSubview(metricsStack)

        [distanceLabel, etaLabel].forEach { label in
            label.textColor = UIColor(red: 0.98, green: 0.94, blue: 0.89, alpha: 1.0)
            label.font = .systemFont(ofSize: 14, weight: .semibold)
            label.numberOfLines = 2
            label.textAlignment = .left
            label.backgroundColor = UIColor(white: 1.0, alpha: 0.05)
            label.layer.cornerRadius = 16
            label.layer.masksToBounds = true
            label.layer.borderWidth = 1
            label.layer.borderColor = UIColor(white: 1.0, alpha: 0.06).cgColor
            label.setContentHuggingPriority(.defaultLow, for: .horizontal)
            label.text = "..."
            metricsStack.addArrangedSubview(label)
        }

        primaryButton.translatesAutoresizingMaskIntoConstraints = false
        primaryButton.backgroundColor = UIColor(red: 1.0, green: 0.74, blue: 0.25, alpha: 1.0)
        primaryButton.setTitleColor(.black, for: .normal)
        primaryButton.titleLabel?.font = .systemFont(ofSize: 17, weight: .bold)
        primaryButton.layer.cornerRadius = 18
        primaryButton.contentEdgeInsets = UIEdgeInsets(top: 14, left: 20, bottom: 14, right: 20)
        primaryButton.setTitle("Zur App", for: .normal)
        primaryButton.addTarget(self, action: #selector(primaryTapped), for: .touchUpInside)
        overlayCard.addSubview(primaryButton)

        NSLayoutConstraint.activate([
            mapView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            mapView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            mapView.topAnchor.constraint(equalTo: view.topAnchor),
            mapView.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            closeButton.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12),
            closeButton.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20),

            overlayCard.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 20),
            overlayCard.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20),
            overlayCard.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -24),

            statusChip.leadingAnchor.constraint(equalTo: overlayCard.leadingAnchor, constant: 20),
            statusChip.topAnchor.constraint(equalTo: overlayCard.topAnchor, constant: 20),
            statusChip.heightAnchor.constraint(equalToConstant: 22),

            titleLabel.leadingAnchor.constraint(equalTo: overlayCard.leadingAnchor, constant: 20),
            titleLabel.trailingAnchor.constraint(equalTo: overlayCard.trailingAnchor, constant: -20),
            titleLabel.topAnchor.constraint(equalTo: statusChip.bottomAnchor, constant: 14),

            bodyLabel.leadingAnchor.constraint(equalTo: overlayCard.leadingAnchor, constant: 20),
            bodyLabel.trailingAnchor.constraint(equalTo: overlayCard.trailingAnchor, constant: -20),
            bodyLabel.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 10),

            metricsStack.leadingAnchor.constraint(equalTo: overlayCard.leadingAnchor, constant: 20),
            metricsStack.trailingAnchor.constraint(equalTo: overlayCard.trailingAnchor, constant: -20),
            metricsStack.topAnchor.constraint(equalTo: bodyLabel.bottomAnchor, constant: 16),

            primaryButton.leadingAnchor.constraint(equalTo: overlayCard.leadingAnchor, constant: 20),
            primaryButton.trailingAnchor.constraint(equalTo: overlayCard.trailingAnchor, constant: -20),
            primaryButton.topAnchor.constraint(equalTo: metricsStack.bottomAnchor, constant: 18),
            primaryButton.bottomAnchor.constraint(equalTo: overlayCard.bottomAnchor, constant: -20)
        ])

        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyBest
        installMeetingPointIfNeeded()
        applyFlowState(.locating)
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        startLocationFlow()
    }

    private func startLocationFlow() {
        guard CLLocationManager.locationServicesEnabled() else {
            applyErrorState("Standort ist auf diesem Geraet gerade nicht verfuegbar.")
            return
        }

        switch locationManager.authorizationStatus {
        case .authorizedAlways, .authorizedWhenInUse:
            activateLocationUpdates()
        case .notDetermined:
            locationManager.requestWhenInUseAuthorization()
        case .denied, .restricted:
            applyErrorState("Standortzugriff wurde nicht freigegeben.")
        @unknown default:
            applyErrorState("MapKit ist gerade nicht verfuegbar.")
        }
    }

    private func activateLocationUpdates() {
        mapView.showsUserLocation = true
        locationManager.startUpdatingLocation()
    }

    private func installMeetingPointIfNeeded() {
        if let existingAnnotation = meetingPointAnnotation {
            mapView.removeAnnotation(existingAnnotation)
            meetingPointAnnotation = nil
        }

        guard let meetingPoint = activeMeetingPoint else { return }
        let annotation = MKPointAnnotation()
        annotation.title = meetingPoint.name
        annotation.subtitle = "Treffpunkt"
        annotation.coordinate = meetingPoint.coordinate
        mapView.addAnnotation(annotation)
        meetingPointAnnotation = annotation
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        startLocationFlow()
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        latestLocation = location

        let region = MKCoordinateRegion(
            center: location.coordinate,
            latitudinalMeters: 450,
            longitudinalMeters: 450
        )
        mapView.setRegion(region, animated: true)
        resolveMeetingPointIfNeeded()
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        let nsError = error as NSError
        if nsError.domain == kCLErrorDomain, nsError.code == CLError.denied.rawValue {
            applyErrorState("Standortzugriff wurde nicht freigegeben.")
            return
        }
        applyErrorState("Dein Standort konnte gerade nicht gelesen werden.")
    }

    @objc
    private func primaryTapped() {
        guard !isSubmittingAction else { return }

        switch flowState {
        case .acceptanceWaitingYou:
            submitMeetingAcceptance()
        case .arrivalWaitingYou:
            submitMeetingArrival()
        case .okWaitingYou:
            submitMeetingOk()
        case .chatUnlocked:
            shouldOpenChatOnFinish = true
            finishCurrentState()
        default:
            finishCurrentState()
        }
    }

    @objc
    private func closeTapped() {
        finishCurrentState()
    }

    private func applyErrorState(_ message: String) {
        applyFlowState(.error, bodyOverride: message)
    }

    private func applyFlowState(_ state: FlowState, bodyOverride: String? = nil) {
        flowState = state

        switch state {
        case .locating:
            statusChip.text = "Standort aktiv"
            titleLabel.text = activeMeetingPoint == nil ? "Standort wird vorbereitet" : "Treffpunkt auf der Karte"
            bodyLabel.text = bodyOverride ?? (activeMeetingPoint == nil
                ? "Dein aktueller Standort wird geladen. Danach fuehrt derselbe native Screen weiter zum Treffpunkt."
                : "Dein Standort wird laufend aktualisiert, damit daraus die native Route entstehen kann.")
            metricsStack.isHidden = true
            primaryButton.setTitle(isSubmittingAction ? "Wird vorbereitet..." : "Zur App", for: .normal)
            primaryButton.isEnabled = !isSubmittingAction
        case .acceptanceWaitingYou:
            statusChip.text = "Wartet auf dich"
            titleLabel.text = activeMeetingPoint?.name ?? "Treffpunkt steht"
            bodyLabel.text = bodyOverride ?? "Der Treffpunkt steht. Bevor die Navigation wirklich frei ist, wartet dieses Meeting noch auf deine Annahme."
            metricsStack.isHidden = true
            primaryButton.setTitle(isSubmittingAction ? "Wird bestaetigt..." : "Annahme bestaetigen", for: .normal)
            primaryButton.isEnabled = !isSubmittingAction
        case .acceptanceWaitingOther:
            statusChip.text = "Wartet auf die andere Person"
            titleLabel.text = activeMeetingPoint?.name ?? "Treffpunkt steht"
            bodyLabel.text = bodyOverride ?? "Du hast das Meeting bereits angenommen. Jetzt wartet der native Flow noch auf die Annahme der anderen Person."
            metricsStack.isHidden = true
            primaryButton.setTitle("Zur App", for: .normal)
            primaryButton.isEnabled = true
        case .acceptanceReady:
            statusChip.text = "Beide haben angenommen"
            titleLabel.text = activeMeetingPoint?.name ?? "Treffpunkt bestaetigt"
            bodyLabel.text = bodyOverride ?? "Beide Seiten haben das Meeting angenommen. Die native Navigation kann direkt im selben Flow weitergehen."
            metricsStack.isHidden = true
            primaryButton.setTitle("Zur App", for: .normal)
            primaryButton.isEnabled = true
        case .meetingPointReady:
            statusChip.text = "Treffpunkt steht"
            titleLabel.text = activeMeetingPoint?.name ?? "Treffpunkt bereit"
            bodyLabel.text = bodyOverride ?? "Der Treffpunkt ist nativ gefunden. Die Route wird direkt in diesem Kartenfluss vorbereitet."
            metricsStack.isHidden = true
            primaryButton.setTitle("Zur App", for: .normal)
            primaryButton.isEnabled = true
        case .navigationActive:
            statusChip.text = "Route aktiv"
            titleLabel.text = activeMeetingPoint?.name ?? "Navigation aktiv"
            bodyLabel.text = bodyOverride ?? "Treffpunkt steht und die native Route ist aktiv. Distanz und Zeit aktualisieren sich aus den echten Karten- und Standortdaten."
            metricsStack.isHidden = false
            distanceLabel.text = "Distanz\n\(formattedDistance(route?.distance))"
            etaLabel.text = "Zeit\n\(formattedDuration(route?.expectedTravelTime))"
            primaryButton.setTitle("Zur App", for: .normal)
            primaryButton.isEnabled = true
        case .arrivalWaitingYou:
            statusChip.text = "Wartet auf deine Ankunft"
            titleLabel.text = activeMeetingPoint?.name ?? "Fast am Treffpunkt"
            bodyLabel.text = bodyOverride ?? "Die Navigation laeuft. Sobald du am Treffpunkt bist, wartet das gemeinsame Meeting auf deine serverseitige Ankunft."
            metricsStack.isHidden = false
            distanceLabel.text = "Distanz\n\(formattedDistance(route?.distance))"
            etaLabel.text = "Zeit\n\(formattedDuration(route?.expectedTravelTime))"
            primaryButton.setTitle(isSubmittingAction ? "Wird bestaetigt..." : "Ankunft bestaetigen", for: .normal)
            primaryButton.isEnabled = !isSubmittingAction
        case .arrivalWaitingOther:
            statusChip.text = "Wartet auf die andere Person"
            titleLabel.text = activeMeetingPoint?.name ?? "Deine Ankunft ist gespeichert"
            bodyLabel.text = bodyOverride ?? "Deine Ankunft ist bereits im gemeinsamen Meeting gespeichert. Jetzt wartet der native Flow noch auf die andere Person."
            metricsStack.isHidden = false
            distanceLabel.text = "Distanz\n\(formattedDistance(route?.distance))"
            etaLabel.text = "Zeit\n\(formattedDuration(route?.expectedTravelTime))"
            primaryButton.setTitle("Zur App", for: .normal)
            primaryButton.isEnabled = true
        case .arrivalReady:
            statusChip.text = "Beide angekommen"
            titleLabel.text = activeMeetingPoint?.name ?? "Ankunft bestaetigt"
            bodyLabel.text = bodyOverride ?? "Beide Ankuenfte sind serverseitig im gemeinsamen Meeting gespeichert. Der Treffpunkt bleibt als gemeinsamer Kartenkontext sichtbar."
            metricsStack.isHidden = false
            distanceLabel.text = "Distanz\n\(formattedDistance(route?.distance))"
            etaLabel.text = "Zeit\n\(formattedDuration(route?.expectedTravelTime))"
            primaryButton.setTitle("Zur App", for: .normal)
            primaryButton.isEnabled = true
        case .okWaitingYou:
            statusChip.text = "Wartet auf dein OK"
            titleLabel.text = activeMeetingPoint?.name ?? "Treffen war gut?"
            bodyLabel.text = bodyOverride ?? "Beide sind angekommen. Wenn das Treffen fuer dich gut war, kannst du jetzt dein serverseitiges OK bestaetigen."
            metricsStack.isHidden = false
            distanceLabel.text = "Distanz\n\(formattedDistance(route?.distance))"
            etaLabel.text = "Zeit\n\(formattedDuration(route?.expectedTravelTime))"
            primaryButton.setTitle(isSubmittingAction ? "Wird bestaetigt..." : "OK bestaetigen", for: .normal)
            primaryButton.isEnabled = !isSubmittingAction
        case .okWaitingOther:
            statusChip.text = "Wartet auf die andere Person"
            titleLabel.text = activeMeetingPoint?.name ?? "Dein OK ist gespeichert"
            bodyLabel.text = bodyOverride ?? "Dein OK ist serverseitig gespeichert. Jetzt wartet das Meeting noch auf die andere Person."
            metricsStack.isHidden = false
            distanceLabel.text = "Distanz\n\(formattedDistance(route?.distance))"
            etaLabel.text = "Zeit\n\(formattedDuration(route?.expectedTravelTime))"
            primaryButton.setTitle("Zur App", for: .normal)
            primaryButton.isEnabled = true
        case .okReady:
            statusChip.text = "Beide haben bestaetigt"
            titleLabel.text = activeMeetingPoint?.name ?? "Treffen abgeschlossen"
            bodyLabel.text = bodyOverride ?? "Beide Seiten haben das Treffen serverseitig bestaetigt. Der Chat kann jetzt freigegeben werden."
            metricsStack.isHidden = false
            distanceLabel.text = "Distanz\n\(formattedDistance(route?.distance))"
            etaLabel.text = "Zeit\n\(formattedDuration(route?.expectedTravelTime))"
            primaryButton.setTitle("Zur App", for: .normal)
            primaryButton.isEnabled = true
        case .chatUnlocked:
            statusChip.text = "Chat freigegeben"
            titleLabel.text = activeMeetingPoint?.name ?? "Ihr seid verbunden"
            bodyLabel.text = bodyOverride ?? "Beide haben bestaetigt. Der serverseitige Chat ist jetzt freigegeben und kann direkt geoeffnet werden."
            metricsStack.isHidden = false
            distanceLabel.text = "Distanz\n\(formattedDistance(route?.distance))"
            etaLabel.text = "Zeit\n\(formattedDuration(route?.expectedTravelTime))"
            primaryButton.setTitle("Zum Chat", for: .normal)
            primaryButton.isEnabled = true
        case .error:
            statusChip.text = "Gerade nicht bereit"
            titleLabel.text = "Navigation nicht verfuegbar"
            bodyLabel.text = bodyOverride ?? "Die native Karte konnte diesen Schritt gerade nicht vollstaendig vorbereiten."
            metricsStack.isHidden = true
            primaryButton.setTitle("Zur App", for: .normal)
            primaryButton.isEnabled = true
        }
    }

    private func acceptanceFlowState() -> FlowState? {
        guard let acceptanceStatus, activeMeetingPoint != nil else { return nil }
        if acceptanceStatus.fullyAccepted { return .acceptanceReady }
        if acceptanceStatus.youAccepted { return .acceptanceWaitingOther }
        return .acceptanceWaitingYou
    }

    private func arrivalFlowState() -> FlowState? {
        guard acceptanceStatus?.fullyAccepted == true, let arrivalStatus, activeMeetingPoint != nil else { return nil }
        if arrivalStatus.bothArrived { return .arrivalReady }
        if arrivalStatus.youArrived { return .arrivalWaitingOther }
        return .arrivalWaitingYou
    }

    private func okFlowState() -> FlowState? {
        guard arrivalStatus?.bothArrived == true, let okStatus, activeMeetingPoint != nil else { return nil }
        if okStatus.chatUnlocked { return .chatUnlocked }
        if okStatus.bothOk { return .okReady }
        if okStatus.youOk { return .okWaitingOther }
        return .okWaitingYou
    }

    private func formattedDistance(_ meters: CLLocationDistance?) -> String {
        guard let meters, meters.isFinite else { return "Wird berechnet" }
        if meters >= 1000 {
            return String(format: "%.1f km", meters / 1000)
        }
        return "\(Int(meters.rounded())) m"
    }

    private func formattedDuration(_ seconds: TimeInterval?) -> String {
        guard let seconds, seconds.isFinite else { return "Wird berechnet" }
        let minutes = max(1, Int((seconds / 60).rounded()))
        return "\(minutes) Min."
    }

    private func updateMapFocus() {
        if let latestLocation, let meetingPoint = activeMeetingPoint {
            let coordinates = [latestLocation.coordinate, meetingPoint.coordinate]
            let mapRect = coordinates.reduce(MKMapRect.null) { partialResult, coordinate in
                let point = MKMapPoint(coordinate)
                let rect = MKMapRect(x: point.x, y: point.y, width: 0, height: 0)
                return partialResult.isNull ? rect : partialResult.union(rect)
            }
            mapView.setVisibleMapRect(
                mapRect,
                edgePadding: UIEdgeInsets(top: 120, left: 56, bottom: 220, right: 56),
                animated: true
            )
            return
        }

        if let meetingPoint = activeMeetingPoint {
            let region = MKCoordinateRegion(
                center: meetingPoint.coordinate,
                latitudinalMeters: 450,
                longitudinalMeters: 450
            )
            mapView.setRegion(region, animated: true)
        }
    }

    private func resolveMeetingPointIfNeeded() {
        guard let latestLocation else {
            bodyLabel.text = "Dein echter Standort ist geladen. Der Treffpunkt wird vorbereitet."
            return
        }

        if activeMeetingPoint != nil {
            updateMapFocus()
            if let acceptanceState = acceptanceFlowState(), route == nil {
                applyFlowState(acceptanceState)
            } else {
                applyFlowState(route == nil ? .meetingPointReady : (okFlowState() ?? arrivalFlowState() ?? .navigationActive))
            }
            calculateRouteIfNeeded()
            return
        }

        guard let candidateLocation else {
            applyFlowState(.error, bodyOverride: "Dein Standort ist geladen, aber fuer den Treffpunkt fehlen noch Daten der anderen Person.")
            routeErrorStatus = "meeting_point_missing"
            return
        }

        guard !isResolvingMeetingPoint else { return }
        isResolvingMeetingPoint = true
        applyFlowState(.locating, bodyOverride: "Ein neutraler Treffpunkt wird nativ gesucht.")

        let midpoint = CLLocationCoordinate2D(
            latitude: (latestLocation.coordinate.latitude + candidateLocation.latitude) / 2,
            longitude: (latestLocation.coordinate.longitude + candidateLocation.longitude) / 2
        )

        searchMeetingPoint(around: midpoint) { [weak self] meetingPoint in
            guard let self else { return }
            self.isResolvingMeetingPoint = false

            guard let meetingPoint else {
                self.routeErrorStatus = "meeting_point_missing"
                self.applyFlowState(.error, bodyOverride: "Es konnte nativerseits kein neutraler Treffpunkt gefunden werden.")
                return
            }

            self.activeMeetingPoint = meetingPoint
            self.installMeetingPointIfNeeded()
            self.updateMapFocus()
            if let acceptanceState = self.acceptanceFlowState() {
                self.applyFlowState(acceptanceState, bodyOverride: "Der Treffpunkt ist gefunden. Die Annahme dieses Meetings wird jetzt im selben nativen Flow sichtbar.")
            } else {
                self.applyFlowState(.meetingPointReady, bodyOverride: "Ein neutraler Treffpunkt wurde nativ gefunden. Die Route wird jetzt vorbereitet.")
            }
            self.calculateRouteIfNeeded()
        }
    }

    private func searchMeetingPoint(
        around coordinate: CLLocationCoordinate2D,
        completion: @escaping (MapMeetingCoordinator.MeetingPoint?) -> Void
    ) {
        let queries = ["cafe", "coffee", "library", "restaurant"]
        searchMeetingPoint(queries: queries, around: coordinate, completion: completion)
    }

    private func searchMeetingPoint(
        queries: [String],
        around coordinate: CLLocationCoordinate2D,
        completion: @escaping (MapMeetingCoordinator.MeetingPoint?) -> Void
    ) {
        guard let query = queries.first else {
            completion(nil)
            return
        }

        let request = MKLocalSearch.Request()
        request.naturalLanguageQuery = query
        request.region = MKCoordinateRegion(center: coordinate, latitudinalMeters: 1200, longitudinalMeters: 1200)

        MKLocalSearch(request: request).start { [weak self] response, error in
            guard let self else { return }

            let items = response?.mapItems ?? []
            if let item = items.first(where: { $0.placemark.location != nil && !($0.name ?? "").isEmpty }),
               let location = item.placemark.location {
                completion(
                    MapMeetingCoordinator.MeetingPoint(
                        name: item.name ?? "Treffpunkt",
                        latitude: location.coordinate.latitude,
                        longitude: location.coordinate.longitude
                    )
                )
                return
            }

            if error != nil {
                self.routeErrorStatus = "directions_failed"
            }

            self.searchMeetingPoint(queries: Array(queries.dropFirst()), around: coordinate, completion: completion)
        }
    }

    private func calculateRouteIfNeeded() {
        guard let latestLocation else {
            route = nil
            routeErrorStatus = "location_unavailable"
            removeRouteOverlay()
            return
        }

        guard let meetingPoint = activeMeetingPoint else {
            route = nil
            routeErrorStatus = "meeting_point_missing"
            removeRouteOverlay()
            return
        }

        directions?.cancel()
        routeErrorStatus = nil

        let request = MKDirections.Request()
        request.source = MKMapItem(placemark: MKPlacemark(coordinate: latestLocation.coordinate))
        request.destination = MKMapItem(placemark: MKPlacemark(coordinate: meetingPoint.coordinate))
        request.transportType = .walking

        let directions = MKDirections(request: request)
        self.directions = directions
        directions.calculate { [weak self] response, error in
            guard let self else { return }

            if let error {
                self.route = nil
                self.removeRouteOverlay()
                let nsError = error as NSError
                if nsError.domain == MKError.errorDomain &&
                    (nsError.code == MKError.placemarkNotFound.rawValue || nsError.code == MKError.directionsNotFound.rawValue) {
                    self.routeErrorStatus = "routing_unavailable"
                } else {
                    self.routeErrorStatus = "directions_failed"
                }
                self.applyFlowState(self.okFlowState() ?? self.arrivalFlowState() ?? self.acceptanceFlowState() ?? .meetingPointReady, bodyOverride: "Treffpunkt steht, aber die native Route konnte gerade nicht berechnet werden.")
                return
            }

            guard let route = response?.routes.first else {
                self.route = nil
                self.removeRouteOverlay()
                self.routeErrorStatus = "routing_unavailable"
                self.applyFlowState(self.okFlowState() ?? self.arrivalFlowState() ?? self.acceptanceFlowState() ?? .meetingPointReady, bodyOverride: "Treffpunkt steht, aber zwischen Standort und Treffpunkt ist gerade keine native Route verfuegbar.")
                return
            }

            self.route = route
            self.routeErrorStatus = nil
            self.removeRouteOverlay()
            self.mapView.addOverlay(route.polyline)
            self.updateMapFocus()
            if let okState = self.okFlowState() {
                self.applyFlowState(okState, bodyOverride: okState == .chatUnlocked
                    ? "Beide haben bestaetigt. Der serverseitige Chat ist jetzt direkt aus diesem nativen Flow erreichbar."
                    : okState == .okWaitingOther
                        ? "Dein OK ist gespeichert. Jetzt wartet das gemeinsame Meeting noch auf die andere Person."
                        : okState == .okReady
                            ? "Beide haben bestaetigt. Die Chat-Freigabe wird ueber denselben serverseitigen Meeting-Status getragen."
                            : "Beide sind angekommen. Wenn das Treffen fuer dich gut war, kannst du jetzt dein serverseitiges OK bestaetigen.")
            } else if let arrivalState = self.arrivalFlowState() {
                self.applyFlowState(arrivalState, bodyOverride: arrivalState == .arrivalWaitingOther
                    ? "Deine Ankunft ist gespeichert. Die native Karte bleibt offen, bis auch die andere Person angekommen ist."
                    : arrivalState == .arrivalReady
                        ? "Beide Ankuenfte sind gespeichert. Der Treffpunkt bleibt als gemeinsamer Kartenkontext sichtbar."
                        : "Die Route ist aktiv. Sobald du am Treffpunkt bist, wartet das Meeting auf deine serverseitige Ankunft.")
            } else if let acceptanceState = self.acceptanceFlowState(), acceptanceStatus?.fullyAccepted != true {
                self.applyFlowState(acceptanceState, bodyOverride: acceptanceState == .acceptanceWaitingOther
                    ? "Die Route ist vorbereitet, aber die Navigation bleibt noch gesperrt, bis die andere Person angenommen hat."
                    : "Die Route ist vorbereitet, aber die Navigation bleibt noch gesperrt, bis du dieses Meeting angenommen hast.")
            } else if acceptanceStatus?.fullyAccepted == true {
                self.applyFlowState(.navigationActive, bodyOverride: "Beide haben angenommen. Die native Route ist jetzt aktiv.")
            } else {
                self.applyFlowState(.navigationActive)
            }
        }
    }

    private func removeRouteOverlay() {
        mapView.removeOverlays(mapView.overlays)
    }

    func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
        if annotation is MKUserLocation {
            return nil
        }

        let identifier = "meeting-point"
        let view = mapView.dequeueReusableAnnotationView(withIdentifier: identifier) as? MKMarkerAnnotationView
            ?? MKMarkerAnnotationView(annotation: annotation, reuseIdentifier: identifier)
        view.annotation = annotation
        view.markerTintColor = UIColor(red: 1.0, green: 0.74, blue: 0.25, alpha: 1.0)
        view.glyphText = "T"
        view.titleVisibility = .adaptive
        view.subtitleVisibility = .adaptive
        return view
    }

    func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
        if let polyline = overlay as? MKPolyline {
            let renderer = MKPolylineRenderer(polyline: polyline)
            renderer.strokeColor = UIColor(red: 1.0, green: 0.74, blue: 0.25, alpha: 0.95)
            renderer.lineWidth = 5
            renderer.lineJoin = .round
            renderer.lineCap = .round
            return renderer
        }

        return MKOverlayRenderer(overlay: overlay)
    }

    private func finishCurrentState() {
        let result: MapMeetingCoordinator.MapResult
        if !CLLocationManager.locationServicesEnabled() {
            result = MapMeetingCoordinator.MapResult(location: nil, accuracy: nil, meetingPoint: activeMeetingPoint, routeMeta: nil, serverMeeting: latestServerMeeting, openChat: shouldOpenChatOnFinish, errorStatus: "location_unavailable")
        } else {
            switch locationManager.authorizationStatus {
            case .denied, .restricted:
                result = MapMeetingCoordinator.MapResult(location: nil, accuracy: nil, meetingPoint: activeMeetingPoint, routeMeta: nil, serverMeeting: latestServerMeeting, openChat: shouldOpenChatOnFinish, errorStatus: "location_denied")
            case .authorizedAlways, .authorizedWhenInUse:
                if let latestLocation {
                    let routeMeta = route.map {
                        MapMeetingCoordinator.MapResult.RouteMeta(
                            distanceMeters: $0.distance,
                            expectedTravelTimeSeconds: $0.expectedTravelTime
                        )
                    }
                    result = MapMeetingCoordinator.MapResult(
                        location: latestLocation.coordinate,
                        accuracy: latestLocation.horizontalAccuracy,
                        meetingPoint: activeMeetingPoint,
                        routeMeta: routeMeta,
                        serverMeeting: latestServerMeeting,
                        openChat: shouldOpenChatOnFinish,
                        errorStatus: routeErrorStatus ?? (activeMeetingPoint == nil ? "meeting_point_missing" : nil)
                    )
                } else {
                    result = MapMeetingCoordinator.MapResult(location: nil, accuracy: nil, meetingPoint: activeMeetingPoint, routeMeta: nil, serverMeeting: latestServerMeeting, openChat: shouldOpenChatOnFinish, errorStatus: "location_unavailable")
                }
            case .notDetermined:
                result = MapMeetingCoordinator.MapResult(location: nil, accuracy: nil, meetingPoint: activeMeetingPoint, routeMeta: nil, serverMeeting: latestServerMeeting, openChat: shouldOpenChatOnFinish, errorStatus: "location_unavailable")
            @unknown default:
                result = MapMeetingCoordinator.MapResult(location: nil, accuracy: nil, meetingPoint: activeMeetingPoint, routeMeta: nil, serverMeeting: latestServerMeeting, openChat: shouldOpenChatOnFinish, errorStatus: "map_unavailable")
            }
        }

        finish(result)
    }

    private func submitMeetingAcceptance() {
        guard let context = meetingContext else {
            applyErrorState("Dieses Meeting kann gerade nicht serverseitig bestaetigt werden.")
            return
        }

        isSubmittingAction = true
        applyFlowState(.acceptanceWaitingYou, bodyOverride: "Deine Annahme wird serverseitig gespeichert.")

        performMeetingRequest(
            endpoint: "/core/meeting/accept",
            body: ["meeting_id": context.meetingId]
        ) { [weak self] result in
            guard let self else { return }
            DispatchQueue.main.async {
                self.isSubmittingAction = false

                switch result {
                case .success(let meeting):
                    self.applyServerMeetingUpdate(meeting)
                case .failure:
                    self.applyFlowState(.acceptanceWaitingYou, bodyOverride: "Deine Annahme konnte gerade nicht gespeichert werden. Bitte versuche es gleich erneut.")
                }
            }
        }
    }

    private func submitMeetingArrival() {
        guard let context = meetingContext else {
            applyErrorState("Dieses Meeting kann gerade nicht serverseitig aktualisiert werden.")
            return
        }
        guard let latestLocation else {
            applyFlowState(.arrivalWaitingYou, bodyOverride: "Dein Standort ist gerade nicht genau genug verfuegbar, um deine Ankunft zu bestaetigen.")
            return
        }

        isSubmittingAction = true
        applyFlowState(.arrivalWaitingYou, bodyOverride: "Deine Ankunft wird serverseitig gespeichert.")

        performMeetingRequest(
            endpoint: "/core/check-in",
            body: [
                "meeting_id": context.meetingId,
                "lat": latestLocation.coordinate.latitude,
                "lng": latestLocation.coordinate.longitude
            ]
        ) { [weak self] result in
            guard let self else { return }
            DispatchQueue.main.async {
                self.isSubmittingAction = false

                switch result {
                case .success(let meeting):
                    self.applyServerMeetingUpdate(meeting)
                case .failure:
                    self.applyFlowState(.arrivalWaitingYou, bodyOverride: "Deine Ankunft konnte gerade nicht gespeichert werden. Bitte versuche es gleich erneut.")
                }
            }
        }
    }

    private func submitMeetingOk() {
        guard let context = meetingContext else {
            applyErrorState("Dieses Meeting kann gerade nicht serverseitig bestaetigt werden.")
            return
        }

        isSubmittingAction = true
        applyFlowState(.okWaitingYou, bodyOverride: "Dein OK wird serverseitig gespeichert.")

        performMeetingRequest(
            endpoint: "/core/ok",
            body: ["meeting_id": context.meetingId, "signal": "ok"]
        ) { [weak self] result in
            guard let self else { return }
            DispatchQueue.main.async {
                self.isSubmittingAction = false

                switch result {
                case .success(let meeting):
                    self.applyServerMeetingUpdate(meeting)
                case .failure:
                    self.applyFlowState(.okWaitingYou, bodyOverride: "Dein OK konnte gerade nicht gespeichert werden. Bitte versuche es gleich erneut.")
                }
            }
        }
    }

    private func performMeetingRequest(
        endpoint: String,
        body: [String: Any],
        completion: @escaping (Result<MapMeetingCoordinator.MapResult.ServerMeetingPayload, Error>) -> Void
    ) {
        guard let context = meetingContext,
              let url = URL(string: context.backendOrigin + endpoint)
        else {
            completion(.failure(NSError(domain: "MapMeeting", code: -1, userInfo: nil)))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(context.authToken)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 20

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        } catch {
            completion(.failure(error))
            return
        }

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error {
                completion(.failure(error))
                return
            }

            guard let httpResponse = response as? HTTPURLResponse,
                  (200..<300).contains(httpResponse.statusCode),
                  let data
            else {
                completion(.failure(NSError(domain: "MapMeeting", code: -2, userInfo: nil)))
                return
            }

            do {
                let jsonObject = try JSONSerialization.jsonObject(with: data) as? [String: Any]
                guard let meetingPayload = jsonObject?["meeting"] as? [String: Any],
                      let meeting = Self.parseServerMeetingPayload(from: meetingPayload)
                else {
                    completion(.failure(NSError(domain: "MapMeeting", code: -3, userInfo: nil)))
                    return
                }
                completion(.success(meeting))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }

    private func applyServerMeetingUpdate(_ meeting: MapMeetingCoordinator.MapResult.ServerMeetingPayload) {
        DispatchQueue.main.async {
            self.latestServerMeeting = meeting
            self.activeMeetingPoint = MapMeetingCoordinator.MeetingPoint(
                name: meeting.spotName,
                latitude: meeting.spotLat,
                longitude: meeting.spotLng
            )
            self.installMeetingPointIfNeeded()
            self.acceptanceStatus = MapMeetingCoordinator.AcceptanceStatus(
                youAccepted: meeting.fullyAccepted || !meeting.acceptedBy.isEmpty,
                otherAccepted: meeting.fullyAccepted || meeting.acceptedBy.count > 1,
                fullyAccepted: meeting.fullyAccepted
            )
            self.arrivalStatus = MapMeetingCoordinator.ArrivalStatus(
                youArrived: meeting.bothArrived || !meeting.arrivedBy.isEmpty,
                otherArrived: meeting.bothArrived || meeting.arrivedBy.count > 1,
                bothArrived: meeting.bothArrived
            )
            self.okStatus = MapMeetingCoordinator.OkStatus(
                youOk: meeting.bothOk || !meeting.okBy.isEmpty,
                otherOk: meeting.bothOk || meeting.okBy.count > 1,
                bothOk: meeting.bothOk,
                chatUnlocked: meeting.chatUnlocked
            )
            self.updateMapFocus()

            if let okState = self.okFlowState() {
                self.applyFlowState(okState)
            } else if let arrivalState = self.arrivalFlowState() {
                self.applyFlowState(arrivalState)
            } else if let acceptanceState = self.acceptanceFlowState(), self.acceptanceStatus?.fullyAccepted != true {
                self.applyFlowState(acceptanceState)
            } else if self.acceptanceStatus?.fullyAccepted == true, self.route != nil {
                self.applyFlowState(.navigationActive, bodyOverride: "Beide haben angenommen. Die native Route ist jetzt aktiv.")
            } else {
                self.applyFlowState(self.route == nil ? .meetingPointReady : .navigationActive)
            }
        }
    }

    private static func parseServerMeetingPayload(from payload: [String: Any]) -> MapMeetingCoordinator.MapResult.ServerMeetingPayload? {
        func number(from value: Any?) -> Double? {
            if let double = value as? Double { return double }
            if let number = value as? NSNumber { return number.doubleValue }
            if let string = value as? String { return Double(string) }
            return nil
        }

        guard let id = payload["id"] as? Int ?? Int(payload["id"] as? String ?? ""),
              let spotName = payload["spot_name"] as? String,
              let spotLat = number(from: payload["spot_lat"]),
              let spotLng = number(from: payload["spot_lng"]),
              let status = payload["status"] as? String
        else {
            return nil
        }

        func stringifyIds(_ values: Any?) -> [String] {
            guard let values = values as? [Any] else { return [] }
            return values.compactMap {
                if let string = $0 as? String { return string }
                if let number = $0 as? NSNumber { return number.stringValue }
                return nil
            }
        }

        return MapMeetingCoordinator.MapResult.ServerMeetingPayload(
            id: id,
            spotName: spotName,
            spotLat: spotLat,
            spotLng: spotLng,
            status: status,
            acceptedBy: stringifyIds(payload["accepted_by"]),
            arrivedBy: stringifyIds(payload["arrived_by"]),
            okBy: stringifyIds(payload["ok_by"]),
            fullyAccepted: payload["fully_accepted"] as? Bool ?? false,
            bothArrived: payload["both_arrived"] as? Bool ?? false,
            bothOk: payload["both_ok"] as? Bool ?? false,
            chatUnlocked: payload["chat_unlocked"] as? Bool ?? false
        )
    }

    private func finish(_ result: MapMeetingCoordinator.MapResult) {
        guard !didFinish else { return }
        didFinish = true
        locationManager.stopUpdatingLocation()
        directions?.cancel()

        dismiss(animated: true) {
            self.completion(result)
        }
    }
}
