#include "G4Box.hh"
#include "G4EmLivermorePhysics.hh"
#include "G4EmParameters.hh"
#include "G4Event.hh"
#include "G4Gamma.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4NistManager.hh"
#include "G4PVPlacement.hh"
#include "G4ParticleGun.hh"
#include "G4PhysicalConstants.hh"
#include "G4RotationMatrix.hh"
#include "G4RunManager.hh"
#include "G4RunManagerFactory.hh"
#include "G4Step.hh"
#include "G4SystemOfUnits.hh"
#include "G4ThreeVector.hh"
#include "G4Track.hh"
#include "G4UserEventAction.hh"
#include "G4UserSteppingAction.hh"
#include "G4VModularPhysicsList.hh"
#include "G4VUserActionInitialization.hh"
#include "G4VUserDetectorConstruction.hh"
#include "G4VUserPrimaryGeneratorAction.hh"
#include "G4Version.hh"
#include "Randomize.hh"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

constexpr double kGaussianFwhmFactor = 2.3548200450309493;
constexpr double kAgKaMinKeV = 21.60;
constexpr double kAgKaMaxKeV = 22.50;
constexpr double kAgKbMinKeV = 24.45;
constexpr double kAgKbMaxKeV = 25.25;

struct Config {
  std::string input = "3_Simulations/results/wp5/wp5_phase_space.csv";
  std::string output = "3_Simulations/results/wp5/wp5_events.csv";
  std::size_t events = 0;
  long seed = 20260728;

  double sample_width_mm = 10.0;
  double sample_height_mm = 10.0;
  double sample_thickness_mm = 0.10;

  double detector_distance_mm = 50.0;
  double detector_angle_deg = 90.0;
  double detector_width_mm = 20.0;
  double detector_height_mm = 20.0;
  double detector_thickness_mm = 2.0;
  double czt_density_g_cm3 = 5.78;

  double world_half_size_mm = 250.0;
  double production_cut_um = 1.0;
  double source_gap_um = 1.0;

  double resolution_noise_fwhm_keV = 0.80;
  double resolution_fraction_fwhm = 0.020;
  int verbose = 0;
};

std::string trim(const std::string& value) {
  const auto first = value.find_first_not_of(" \t\r\n");
  if (first == std::string::npos) {
    return "";
  }
  const auto last = value.find_last_not_of(" \t\r\n");
  return value.substr(first, last - first + 1);
}

std::vector<std::string> split_csv(const std::string& line) {
  std::vector<std::string> fields;
  std::stringstream stream(line);
  std::string field;
  while (std::getline(stream, field, ',')) {
    fields.push_back(trim(field));
  }
  if (!line.empty() && line.back() == ',') {
    fields.emplace_back();
  }
  return fields;
}

double parse_double(const std::string& text, const std::string& option) {
  std::size_t consumed = 0;
  double value = 0.0;
  try {
    value = std::stod(text, &consumed);
  } catch (const std::exception&) {
    throw std::runtime_error(option + " requires a numeric value, got '" + text + "'");
  }
  if (consumed != text.size() || !std::isfinite(value)) {
    throw std::runtime_error(option + " requires a finite numeric value, got '" + text + "'");
  }
  return value;
}

long parse_long(const std::string& text, const std::string& option) {
  std::size_t consumed = 0;
  long value = 0;
  try {
    value = std::stol(text, &consumed);
  } catch (const std::exception&) {
    throw std::runtime_error(option + " requires an integer value, got '" + text + "'");
  }
  if (consumed != text.size()) {
    throw std::runtime_error(option + " requires an integer value, got '" + text + "'");
  }
  return value;
}

std::size_t parse_size(const std::string& text, const std::string& option) {
  const long value = parse_long(text, option);
  if (value < 0) {
    throw std::runtime_error(option + " cannot be negative");
  }
  return static_cast<std::size_t>(value);
}

void print_help(const Config& defaults, const char* executable) {
  std::cout
      << "PRISM WP5: Ag fluorescence and CZT response with Geant4\n\n"
      << "Usage: " << executable << " [options]\n\n"
      << "Input/output:\n"
      << "  --input PATH                    Prepared phase-space CSV (default: "
      << defaults.input << ")\n"
      << "  --output PATH                   Raw event CSV (default: " << defaults.output
      << ")\n"
      << "  --events N                     Events to run; 0 uses every CSV row (default: "
      << defaults.events << ")\n"
      << "  --seed N                       Geant4 random seed (default: " << defaults.seed
      << ")\n\n"
      << "Ag sample, centred at the origin with beam along +y:\n"
      << "  --sample-width-mm X            Sample extent along x (default: "
      << defaults.sample_width_mm << ")\n"
      << "  --sample-height-mm X           Sample extent along z (default: "
      << defaults.sample_height_mm << ")\n"
      << "  --sample-thickness-mm X        Sample thickness along y (default: "
      << defaults.sample_thickness_mm << ")\n\n"
      << "CZT detector, face directed at the sample:\n"
      << "  --detector-distance-mm X       Sample centre to detector front face (default: "
      << defaults.detector_distance_mm << ")\n"
      << "  --detector-angle-deg X         Angle from +y toward +x (default: "
      << defaults.detector_angle_deg << ")\n"
      << "  --detector-width-mm X          CZT active width (default: "
      << defaults.detector_width_mm << ")\n"
      << "  --detector-height-mm X         CZT active height (default: "
      << defaults.detector_height_mm << ")\n"
      << "  --detector-thickness-mm X      CZT active thickness (default: "
      << defaults.detector_thickness_mm << ")\n"
      << "  --czt-density-g-cm3 X          Cd0.9Zn0.1Te density (default: "
      << defaults.czt_density_g_cm3 << ")\n\n"
      << "Physics and response:\n"
      << "  --production-cut-um X          Global production cut (default: "
      << defaults.production_cut_um << ")\n"
      << "  --source-gap-um X              Gap before sample entrance (default: "
      << defaults.source_gap_um << ")\n"
      << "  --world-half-size-mm X         Vacuum world half size (default: "
      << defaults.world_half_size_mm << ")\n"
      << "  --resolution-noise-fwhm-keV X  Constant CZT FWHM term (default: "
      << defaults.resolution_noise_fwhm_keV << ")\n"
      << "  --resolution-fraction-fwhm X   Fractional CZT FWHM term (default: "
      << defaults.resolution_fraction_fwhm << ")\n"
      << "  --verbose N                    Geant4 verbosity level (default: "
      << defaults.verbose << ")\n"
      << "  -h, --help                     Show this help and exit\n\n"
      << "The input coordinate convention is x/z transverse, +y along the incident\n"
      << "central ray. CSV positions are placed at the Ag entrance surface; the\n"
      << "prepared event weight is carried as normalization metadata, not as a\n"
      << "Geant4 statistical track weight.\n";
}

Config parse_arguments(int argc, char** argv) {
  Config config;
  const Config defaults;

  auto next_value = [&](int& index, const std::string& option) -> std::string {
    if (index + 1 >= argc) {
      throw std::runtime_error(option + " requires a value");
    }
    ++index;
    return argv[index];
  };

  for (int index = 1; index < argc; ++index) {
    const std::string option = argv[index];
    if (option == "--help" || option == "-h") {
      print_help(defaults, argv[0]);
      std::exit(EXIT_SUCCESS);
    } else if (option == "--input") {
      config.input = next_value(index, option);
    } else if (option == "--output") {
      config.output = next_value(index, option);
    } else if (option == "--events") {
      config.events = parse_size(next_value(index, option), option);
    } else if (option == "--seed") {
      config.seed = parse_long(next_value(index, option), option);
    } else if (option == "--sample-width-mm") {
      config.sample_width_mm = parse_double(next_value(index, option), option);
    } else if (option == "--sample-height-mm") {
      config.sample_height_mm = parse_double(next_value(index, option), option);
    } else if (option == "--sample-thickness-mm") {
      config.sample_thickness_mm = parse_double(next_value(index, option), option);
    } else if (option == "--detector-distance-mm") {
      config.detector_distance_mm = parse_double(next_value(index, option), option);
    } else if (option == "--detector-angle-deg") {
      config.detector_angle_deg = parse_double(next_value(index, option), option);
    } else if (option == "--detector-width-mm") {
      config.detector_width_mm = parse_double(next_value(index, option), option);
    } else if (option == "--detector-height-mm") {
      config.detector_height_mm = parse_double(next_value(index, option), option);
    } else if (option == "--detector-thickness-mm") {
      config.detector_thickness_mm = parse_double(next_value(index, option), option);
    } else if (option == "--czt-density-g-cm3") {
      config.czt_density_g_cm3 = parse_double(next_value(index, option), option);
    } else if (option == "--world-half-size-mm") {
      config.world_half_size_mm = parse_double(next_value(index, option), option);
    } else if (option == "--production-cut-um") {
      config.production_cut_um = parse_double(next_value(index, option), option);
    } else if (option == "--source-gap-um") {
      config.source_gap_um = parse_double(next_value(index, option), option);
    } else if (option == "--resolution-noise-fwhm-keV") {
      config.resolution_noise_fwhm_keV =
          parse_double(next_value(index, option), option);
    } else if (option == "--resolution-fraction-fwhm") {
      config.resolution_fraction_fwhm =
          parse_double(next_value(index, option), option);
    } else if (option == "--verbose") {
      config.verbose = static_cast<int>(parse_long(next_value(index, option), option));
    } else {
      throw std::runtime_error("unknown option '" + option + "'; use --help");
    }
  }

  const std::vector<std::pair<std::string, double>> positive_values = {
      {"sample width", config.sample_width_mm},
      {"sample height", config.sample_height_mm},
      {"sample thickness", config.sample_thickness_mm},
      {"detector distance", config.detector_distance_mm},
      {"detector width", config.detector_width_mm},
      {"detector height", config.detector_height_mm},
      {"detector thickness", config.detector_thickness_mm},
      {"CZT density", config.czt_density_g_cm3},
      {"world half size", config.world_half_size_mm},
      {"production cut", config.production_cut_um},
  };
  for (const auto& item : positive_values) {
    if (!(item.second > 0.0)) {
      throw std::runtime_error(item.first + " must be positive");
    }
  }
  if (config.source_gap_um < 0.0 || config.resolution_noise_fwhm_keV < 0.0 ||
      config.resolution_fraction_fwhm < 0.0 || config.verbose < 0) {
    throw std::runtime_error(
        "source gap, response terms, and verbosity cannot be negative");
  }
  if (!(config.detector_angle_deg >= 0.0 && config.detector_angle_deg <= 180.0)) {
    throw std::runtime_error("detector angle must lie in [0, 180] degrees");
  }
  const double farthest_mm =
      config.detector_distance_mm + config.detector_thickness_mm +
      0.5 * std::max(config.detector_width_mm, config.detector_height_mm);
  if (farthest_mm >= config.world_half_size_mm) {
    throw std::runtime_error("detector does not fit inside the configured world");
  }
  if (config.seed <= 0) {
    throw std::runtime_error("seed must be positive");
  }
  return config;
}

struct PhaseSpaceRow {
  std::int64_t phase_event_id = 0;
  std::int64_t source_row = -1;
  double source_weight = 1.0;
  double x_mm = 0.0;
  double y_mm = 0.0;
  double z_mm = 0.0;
  double dx = 0.0;
  double dy = 1.0;
  double dz = 0.0;
  double energy_keV = 25.52;
};

class PhaseSpaceTable {
 public:
  explicit PhaseSpaceTable(const std::string& path) { load(path); }

  const std::vector<PhaseSpaceRow>& rows() const { return rows_; }
  const std::map<std::string, std::string>& metadata() const { return metadata_; }

  double normalization_weight_per_event() const {
    const auto found = metadata_.find("normalization_weight_per_event");
    if (found == metadata_.end()) {
      throw std::runtime_error(
          "phase-space metadata is missing "
          "'normalization_weight_per_event'");
    }
    const double value =
        parse_double(found->second, "normalization_weight_per_event metadata");
    if (!(value > 0.0)) {
      throw std::runtime_error(
          "normalization_weight_per_event metadata must be positive");
    }
    return value;
  }

 private:
  static std::size_t require_column(
      const std::unordered_map<std::string, std::size_t>& columns,
      const std::string& name) {
    const auto found = columns.find(name);
    if (found == columns.end()) {
      throw std::runtime_error("phase-space CSV is missing column '" + name + "'");
    }
    return found->second;
  }

  void load(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) {
      throw std::runtime_error("cannot open phase-space CSV '" + path + "'");
    }

    std::string line;
    std::vector<std::string> header;
    std::size_t line_number = 0;
    while (std::getline(stream, line)) {
      ++line_number;
      line = trim(line);
      if (line.empty()) {
        continue;
      }
      if (line.front() == '#') {
        const std::string comment = trim(line.substr(1));
        const auto separator = comment.find('=');
        if (separator != std::string::npos) {
          metadata_[trim(comment.substr(0, separator))] =
              trim(comment.substr(separator + 1));
        }
        continue;
      }
      if (header.empty()) {
        header = split_csv(line);
        break;
      }
    }
    if (header.empty()) {
      throw std::runtime_error("phase-space CSV has no header");
    }
    const auto schema = metadata_.find("schema");
    if (schema == metadata_.end() ||
        schema->second != "PRISM_WP5_PHASE_SPACE_V1") {
      throw std::runtime_error(
          "phase-space CSV must declare schema=PRISM_WP5_PHASE_SPACE_V1");
    }
    if (metadata_.find("normalization_weight_per_event") == metadata_.end()) {
      throw std::runtime_error(
          "phase-space CSV must declare normalization_weight_per_event");
    }

    std::unordered_map<std::string, std::size_t> columns;
    for (std::size_t index = 0; index < header.size(); ++index) {
      columns[header[index]] = index;
    }
    const std::size_t event_col = require_column(columns, "event_id");
    const std::size_t x_col = require_column(columns, "x_mm");
    const std::size_t y_col = require_column(columns, "y_mm");
    const std::size_t z_col = require_column(columns, "z_mm");
    const std::size_t dx_col = require_column(columns, "dx");
    const std::size_t dy_col = require_column(columns, "dy");
    const std::size_t dz_col = require_column(columns, "dz");
    const std::size_t energy_col = require_column(columns, "energy_keV");
    const std::size_t unit_weight_col = require_column(columns, "unit_weight");
    const std::size_t source_row_col = require_column(columns, "source_row");
    const std::size_t source_weight_col =
        require_column(columns, "source_weight");

    const auto value_at = [&](const std::vector<std::string>& fields,
                              std::size_t column, const std::string& name) {
      if (column >= fields.size()) {
        throw std::runtime_error(
            "phase-space CSV line " + std::to_string(line_number) +
            " has no value for '" + name + "'");
      }
      return parse_double(fields[column], name);
    };

    while (std::getline(stream, line)) {
      ++line_number;
      line = trim(line);
      if (line.empty() || line.front() == '#') {
        continue;
      }
      const auto fields = split_csv(line);
      PhaseSpaceRow row;
      row.phase_event_id = static_cast<std::int64_t>(
          value_at(fields, event_col, "event_id"));
      row.x_mm = value_at(fields, x_col, "x_mm");
      row.y_mm = value_at(fields, y_col, "y_mm");
      row.z_mm = value_at(fields, z_col, "z_mm");
      row.dx = value_at(fields, dx_col, "dx");
      row.dy = value_at(fields, dy_col, "dy");
      row.dz = value_at(fields, dz_col, "dz");
      row.energy_keV = value_at(fields, energy_col, "energy_keV");
      const double unit_weight =
          value_at(fields, unit_weight_col, "unit_weight");
      if (!std::isfinite(unit_weight) ||
          std::abs(unit_weight - 1.0) > 1.0e-12) {
        throw std::runtime_error(
            "phase-space CSV line " + std::to_string(line_number) +
            " must have unit_weight=1");
      }
      row.source_row = static_cast<std::int64_t>(
          value_at(fields, source_row_col, "source_row"));
      row.source_weight =
          value_at(fields, source_weight_col, "source_weight");

      const double direction_norm =
          std::sqrt(row.dx * row.dx + row.dy * row.dy + row.dz * row.dz);
      if (!(direction_norm > 0.0) || !std::isfinite(direction_norm)) {
        throw std::runtime_error(
            "phase-space CSV line " + std::to_string(line_number) +
            " has an invalid direction");
      }
      row.dx /= direction_norm;
      row.dy /= direction_norm;
      row.dz /= direction_norm;
      if (!(row.energy_keV > 0.0) || !(row.source_weight > 0.0)) {
        throw std::runtime_error(
            "phase-space CSV line " + std::to_string(line_number) +
            " has non-positive energy or source weight");
      }
      rows_.push_back(row);
    }
    if (rows_.empty()) {
      throw std::runtime_error("phase-space CSV contains no event rows");
    }
    const auto requested = metadata_.find("requested_events");
    if (requested == metadata_.end()) {
      throw std::runtime_error(
          "phase-space metadata is missing 'requested_events'");
    }
    const std::size_t requested_events =
        parse_size(requested->second, "requested_events metadata");
    if (requested_events == 0 || requested_events != rows_.size()) {
      throw std::runtime_error(
          "requested_events metadata (" + std::to_string(requested_events) +
          ") does not match the number of CSV event rows (" +
          std::to_string(rows_.size()) + ")");
    }
  }

  std::vector<PhaseSpaceRow> rows_;
  std::map<std::string, std::string> metadata_;
};

class DetectorConstruction final : public G4VUserDetectorConstruction {
 public:
  explicit DetectorConstruction(Config config) : config_(std::move(config)) {}

  G4VPhysicalVolume* Construct() override {
    auto* nist = G4NistManager::Instance();
    auto* vacuum = nist->FindOrBuildMaterial("G4_Galactic");
    auto* silver = nist->FindOrBuildMaterial("G4_Ag");

    auto* cadmium = nist->FindOrBuildElement("Cd");
    auto* zinc = nist->FindOrBuildElement("Zn");
    auto* tellurium = nist->FindOrBuildElement("Te");
    constexpr double cd_mass = 0.9 * 112.414;
    constexpr double zn_mass = 0.1 * 65.38;
    constexpr double te_mass = 127.60;
    constexpr double formula_mass = cd_mass + zn_mass + te_mass;
    auto* czt = new G4Material(
        "CZT_Cd0.9Zn0.1Te", config_.czt_density_g_cm3 * g / cm3, 3);
    czt->AddElement(cadmium, cd_mass / formula_mass);
    czt->AddElement(zinc, zn_mass / formula_mass);
    czt->AddElement(tellurium, te_mass / formula_mass);

    auto* world_solid = new G4Box(
        "WorldSolid", config_.world_half_size_mm * mm,
        config_.world_half_size_mm * mm, config_.world_half_size_mm * mm);
    auto* world_logical =
        new G4LogicalVolume(world_solid, vacuum, "WorldLogical");
    auto* world_physical = new G4PVPlacement(
        nullptr, {}, world_logical, "World", nullptr, false, 0, true);

    auto* sample_solid = new G4Box(
        "AgSampleSolid", 0.5 * config_.sample_width_mm * mm,
        0.5 * config_.sample_thickness_mm * mm,
        0.5 * config_.sample_height_mm * mm);
    sample_logical_ =
        new G4LogicalVolume(sample_solid, silver, "AgSampleLogical");
    new G4PVPlacement(
        nullptr, {}, sample_logical_, "AgSample", world_logical, false, 0, true);

    auto* czt_solid = new G4Box(
        "CZTActiveSolid", 0.5 * config_.detector_width_mm * mm,
        0.5 * config_.detector_thickness_mm * mm,
        0.5 * config_.detector_height_mm * mm);
    czt_logical_ =
        new G4LogicalVolume(czt_solid, czt, "CZTActiveLogical");

    const double angle = config_.detector_angle_deg * deg;
    const G4ThreeVector radial(std::sin(angle), std::cos(angle), 0.0);
    const double detector_center_distance =
        (config_.detector_distance_mm +
         0.5 * config_.detector_thickness_mm) *
        mm;
    auto* rotation = new G4RotationMatrix();
    rotation->rotateZ(-angle);
    new G4PVPlacement(
        rotation, detector_center_distance * radial, czt_logical_, "CZTActive",
        world_logical, false, 0, true);

    return world_physical;
  }

  G4LogicalVolume* sample_logical() const { return sample_logical_; }
  G4LogicalVolume* czt_logical() const { return czt_logical_; }
  const Config& config() const { return config_; }

 private:
  Config config_;
  G4LogicalVolume* sample_logical_ = nullptr;
  G4LogicalVolume* czt_logical_ = nullptr;
};

class PhysicsList final : public G4VModularPhysicsList {
 public:
  explicit PhysicsList(double production_cut_um) {
    SetVerboseLevel(0);
    defaultCutValue = production_cut_um * um;
    RegisterPhysics(new G4EmLivermorePhysics(0));

    auto* parameters = G4EmParameters::Instance();
    parameters->SetFluo(true);
    parameters->SetAuger(true);
    parameters->SetPixe(true);
    parameters->SetDeexcitationIgnoreCut(true);
    parameters->SetMinEnergy(10.0 * eV);
    parameters->SetLowestElectronEnergy(10.0 * eV);
  }

  void SetCuts() override { SetCutsWithDefault(); }
};

struct EventRecord {
  PhaseSpaceRow source;
  bool source_set = false;
  double normalization_weight = 1.0;
  double edep_total_keV = 0.0;
  double edep_primary_keV = 0.0;
  double edep_secondary_keV = 0.0;
  double edep_gamma_keV = 0.0;
  double edep_electron_keV = 0.0;
  double edep_other_keV = 0.0;
  int secondary_gamma_created = 0;
  int ag_ka_created = 0;
  int ag_kb_created = 0;
  int secondary_gamma_entered_czt = 0;
  int ag_ka_entered_czt = 0;
  int ag_kb_entered_czt = 0;
  double entered_gamma_energy_sum_keV = 0.0;
};

class OutputWriter {
 public:
  OutputWriter(
      const Config& config, const PhaseSpaceTable& phase_space,
      std::size_t events_to_run, double normalization_weight_per_event)
      : stream_(config.output) {
    if (!stream_) {
      throw std::runtime_error("cannot create raw event CSV '" + config.output + "'");
    }
    stream_ << std::setprecision(12);
    stream_ << "# schema=PRISM_WP5_RAW_V1\n";
    stream_ << "# geant4_version=" << G4Version << "\n";
    stream_ << "# source_csv=" << config.input << "\n";
    stream_ << "# simulated_events=" << events_to_run << "\n";
    stream_ << "# prepared_events_available=" << phase_space.rows().size() << "\n";
    stream_ << "# normalization_weight_per_event="
            << normalization_weight_per_event << "\n";
    stream_ << "# normalization_rescaled_for_event_subset="
            << (events_to_run < phase_space.rows().size() ? "true" : "false")
            << "\n";
    stream_ << "# seed=" << config.seed << "\n";
    stream_ << "# physics=G4EmLivermorePhysics\n";
    stream_ << "# fluorescence=true\n";
    stream_ << "# auger=true\n";
    stream_ << "# pixe=true\n";
    stream_ << "# production_cut_um=" << config.production_cut_um << "\n";
    stream_ << "# sample_material=G4_Ag\n";
    stream_ << "# sample_width_mm=" << config.sample_width_mm << "\n";
    stream_ << "# sample_height_mm=" << config.sample_height_mm << "\n";
    stream_ << "# sample_thickness_mm=" << config.sample_thickness_mm << "\n";
    stream_ << "# detector_material=Cd0.9Zn0.1Te\n";
    stream_ << "# detector_distance_mm=" << config.detector_distance_mm << "\n";
    stream_ << "# detector_angle_deg=" << config.detector_angle_deg << "\n";
    stream_ << "# detector_width_mm=" << config.detector_width_mm << "\n";
    stream_ << "# detector_height_mm=" << config.detector_height_mm << "\n";
    stream_ << "# detector_thickness_mm=" << config.detector_thickness_mm << "\n";
    stream_ << "# czt_density_g_cm3=" << config.czt_density_g_cm3 << "\n";
    stream_ << "# resolution_noise_fwhm_keV="
            << config.resolution_noise_fwhm_keV << "\n";
    stream_ << "# resolution_fraction_fwhm="
            << config.resolution_fraction_fwhm << "\n";
    stream_ << "# ag_ka_roi_keV=" << kAgKaMinKeV << ":" << kAgKaMaxKeV << "\n";
    stream_ << "# ag_kb_roi_keV=" << kAgKbMinKeV << ":" << kAgKbMaxKeV << "\n";
    for (const auto& item : phase_space.metadata()) {
      stream_ << "# source." << item.first << "=" << item.second << "\n";
    }
    stream_
        << "event_id,phase_event_id,source_row,source_weight,"
           "normalization_weight,x_mm,y_mm,z_mm,dx,dy,dz,source_energy_keV,"
           "edep_total_keV,edep_primary_keV,edep_secondary_keV,"
           "edep_gamma_keV,edep_electron_keV,edep_other_keV,"
           "smeared_edep_keV,secondary_gamma_created,ag_ka_created,"
           "ag_kb_created,secondary_gamma_entered_czt,ag_ka_entered_czt,"
           "ag_kb_entered_czt,entered_gamma_energy_sum_keV\n";
  }

  void write(
      int event_id, const EventRecord& record, double smeared_edep_keV) {
    if (!record.source_set) {
      throw std::runtime_error("event ended without source metadata");
    }
    const auto& source = record.source;
    stream_
        << event_id << ',' << source.phase_event_id << ',' << source.source_row
        << ',' << source.source_weight << ',' << record.normalization_weight
        << ',' << source.x_mm << ',' << source.y_mm << ',' << source.z_mm << ','
        << source.dx << ',' << source.dy << ',' << source.dz << ','
        << source.energy_keV << ',' << record.edep_total_keV << ','
        << record.edep_primary_keV << ',' << record.edep_secondary_keV << ','
        << record.edep_gamma_keV << ',' << record.edep_electron_keV << ','
        << record.edep_other_keV << ',' << smeared_edep_keV << ','
        << record.secondary_gamma_created << ',' << record.ag_ka_created << ','
        << record.ag_kb_created << ','
        << record.secondary_gamma_entered_czt << ','
        << record.ag_ka_entered_czt << ',' << record.ag_kb_entered_czt << ','
        << record.entered_gamma_energy_sum_keV << '\n';
  }

 private:
  std::ofstream stream_;
};

class EventAction final : public G4UserEventAction {
 public:
  EventAction(
      OutputWriter* writer, const std::vector<PhaseSpaceRow>* rows,
      double normalization_weight,
      double noise_fwhm_keV, double fractional_fwhm)
      : writer_(writer),
        rows_(rows),
        normalization_weight_(normalization_weight),
        noise_fwhm_keV_(noise_fwhm_keV),
        fractional_fwhm_(fractional_fwhm) {}

  void BeginOfEventAction(const G4Event* event) override {
    record_ = EventRecord{};
    record_.normalization_weight = normalization_weight_;
    const auto event_index = static_cast<std::size_t>(event->GetEventID());
    if (event_index >= rows_->size()) {
      throw std::runtime_error(
          "event index exceeds prepared phase-space row count");
    }
    record_.source = rows_->at(event_index);
    record_.source_set = true;
  }

  void EndOfEventAction(const G4Event* event) override {
    const double raw = record_.edep_total_keV;
    const double fwhm = std::sqrt(
        noise_fwhm_keV_ * noise_fwhm_keV_ +
        std::pow(fractional_fwhm_ * raw, 2));
    const double sigma = fwhm / kGaussianFwhmFactor;
    const double smeared =
        raw > 0.0
            ? std::max(0.0, sigma > 0.0 ? G4RandGauss::shoot(raw, sigma) : raw)
            : 0.0;
    writer_->write(event->GetEventID(), record_, smeared);
  }

  void add_edep(
      double edep_keV, bool primary, const std::string& particle_name) {
    record_.edep_total_keV += edep_keV;
    if (primary) {
      record_.edep_primary_keV += edep_keV;
    } else {
      record_.edep_secondary_keV += edep_keV;
    }
    if (particle_name == "gamma") {
      record_.edep_gamma_keV += edep_keV;
    } else if (particle_name == "e-" || particle_name == "e+") {
      record_.edep_electron_keV += edep_keV;
    } else {
      record_.edep_other_keV += edep_keV;
    }
  }

  void add_secondary_gamma_created(double energy_keV) {
    ++record_.secondary_gamma_created;
    if (energy_keV >= kAgKaMinKeV && energy_keV < kAgKaMaxKeV) {
      ++record_.ag_ka_created;
    } else if (energy_keV >= kAgKbMinKeV && energy_keV < kAgKbMaxKeV) {
      ++record_.ag_kb_created;
    }
  }

  void add_secondary_gamma_entered_czt(double energy_keV) {
    ++record_.secondary_gamma_entered_czt;
    record_.entered_gamma_energy_sum_keV += energy_keV;
    if (energy_keV >= kAgKaMinKeV && energy_keV < kAgKaMaxKeV) {
      ++record_.ag_ka_entered_czt;
    } else if (energy_keV >= kAgKbMinKeV && energy_keV < kAgKbMaxKeV) {
      ++record_.ag_kb_entered_czt;
    }
  }

 private:
  OutputWriter* writer_;
  const std::vector<PhaseSpaceRow>* rows_;
  double normalization_weight_;
  double noise_fwhm_keV_;
  double fractional_fwhm_;
  EventRecord record_;
};

class PrimaryGeneratorAction final : public G4VUserPrimaryGeneratorAction {
 public:
  PrimaryGeneratorAction(
      const std::vector<PhaseSpaceRow>* rows, const Config* config)
      : rows_(rows),
        config_(config),
        gun_(std::make_unique<G4ParticleGun>(1)) {
    gun_->SetParticleDefinition(G4Gamma::GammaDefinition());
  }

  void GeneratePrimaries(G4Event* event) override {
    const auto event_index = static_cast<std::size_t>(event->GetEventID());
    if (event_index >= rows_->size()) {
      throw std::runtime_error(
          "event index exceeds prepared phase-space row count");
    }
    const auto& source = rows_->at(event_index);

    const double entrance_y =
        -0.5 * config_->sample_thickness_mm * mm -
        config_->source_gap_um * um;
    gun_->SetParticlePosition(
        G4ThreeVector(source.x_mm * mm, entrance_y + source.y_mm * mm,
                      source.z_mm * mm));
    gun_->SetParticleMomentumDirection(
        G4ThreeVector(source.dx, source.dy, source.dz));
    gun_->SetParticleEnergy(source.energy_keV * keV);
    gun_->GeneratePrimaryVertex(event);
  }

 private:
  const std::vector<PhaseSpaceRow>* rows_;
  const Config* config_;
  std::unique_ptr<G4ParticleGun> gun_;
};

class SteppingAction final : public G4UserSteppingAction {
 public:
  SteppingAction(
      const DetectorConstruction* detector, EventAction* event_action)
      : detector_(detector), event_action_(event_action) {}

  void UserSteppingAction(const G4Step* step) override {
    const auto* track = step->GetTrack();
    const auto* pre_point = step->GetPreStepPoint();
    const auto* volume =
        pre_point->GetTouchableHandle()->GetVolume() != nullptr
            ? pre_point->GetTouchableHandle()->GetVolume()->GetLogicalVolume()
            : nullptr;
    const std::string particle_name =
        track->GetParticleDefinition()->GetParticleName();

    if (volume == detector_->czt_logical()) {
      const double edep_keV = step->GetTotalEnergyDeposit() / keV;
      if (edep_keV > 0.0) {
        event_action_->add_edep(
            edep_keV, track->GetParentID() == 0, particle_name);
      }
      if (pre_point->GetStepStatus() == fGeomBoundary &&
          particle_name == "gamma" && track->GetParentID() > 0) {
        event_action_->add_secondary_gamma_entered_czt(
            pre_point->GetKineticEnergy() / keV);
      }
    }

    if (volume == detector_->sample_logical() &&
        track->GetCurrentStepNumber() == 1 && track->GetParentID() > 0 &&
        particle_name == "gamma") {
      event_action_->add_secondary_gamma_created(track->GetKineticEnergy() / keV);
    }
  }

 private:
  const DetectorConstruction* detector_;
  EventAction* event_action_;
};

class ActionInitialization final : public G4VUserActionInitialization {
 public:
  ActionInitialization(
      const DetectorConstruction* detector,
      const std::vector<PhaseSpaceRow>* rows, const Config* config,
      OutputWriter* writer, double normalization_weight)
      : detector_(detector),
        rows_(rows),
        config_(config),
        writer_(writer),
        normalization_weight_(normalization_weight) {}

  void Build() const override {
    auto* event_action = new EventAction(
        writer_, rows_, normalization_weight_,
        config_->resolution_noise_fwhm_keV, config_->resolution_fraction_fwhm);
    SetUserAction(event_action);
    SetUserAction(new PrimaryGeneratorAction(rows_, config_));
    SetUserAction(new SteppingAction(detector_, event_action));
  }

 private:
  const DetectorConstruction* detector_;
  const std::vector<PhaseSpaceRow>* rows_;
  const Config* config_;
  OutputWriter* writer_;
  double normalization_weight_;
};

}  // namespace

int main(int argc, char** argv) {
  try {
    const Config config = parse_arguments(argc, argv);
    const PhaseSpaceTable phase_space(config.input);
    const std::size_t available_events = phase_space.rows().size();
    const std::size_t events_to_run =
        config.events == 0 ? available_events : config.events;
    if (events_to_run == 0 || events_to_run > available_events) {
      throw std::runtime_error(
          "--events must be between 1 and the number of prepared CSV rows (" +
          std::to_string(available_events) + "), or zero for all rows");
    }
    const double normalization_weight_per_event =
        phase_space.normalization_weight_per_event() *
        static_cast<double>(available_events) /
        static_cast<double>(events_to_run);
    if (!(normalization_weight_per_event > 0.0) ||
        !std::isfinite(normalization_weight_per_event)) {
      throw std::runtime_error(
          "effective normalization weight per event is invalid");
    }

    G4Random::setTheSeed(config.seed);
    auto* run_manager =
        G4RunManagerFactory::CreateRunManager(G4RunManagerType::Serial);
    run_manager->SetVerboseLevel(config.verbose);

    auto* detector = new DetectorConstruction(config);
    run_manager->SetUserInitialization(detector);
    run_manager->SetUserInitialization(new PhysicsList(config.production_cut_um));

    OutputWriter writer(
        config, phase_space, events_to_run,
        normalization_weight_per_event);
    run_manager->SetUserInitialization(new ActionInitialization(
        detector, &phase_space.rows(), &config, &writer,
        normalization_weight_per_event));

    run_manager->Initialize();
    run_manager->BeamOn(static_cast<G4int>(events_to_run));
    delete run_manager;

    std::cout << "WP5 completed: " << events_to_run << " events -> "
              << config.output << '\n';
    return EXIT_SUCCESS;
  } catch (const std::exception& error) {
    std::cerr << "prism_wp5: " << error.what() << '\n';
    return EXIT_FAILURE;
  }
}
