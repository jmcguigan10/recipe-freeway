#!/usr/bin/env ruby
# frozen_string_literal: true

require "erb"
require "fileutils"
require "optparse"

config = {
  particle: "e+",
  particle_tag: "e_pos",
  part: "0",
  beam_momentum: "159.279",
  n_events: "675847",
  seed_1: "1778753222",
  seed_2: "1778753290",
  run_tag: nil
}

OptionParser.new do |opts|
  opts.banner = "Usage: render-macro.rb [options]"

  opts.on("--template PATH", "Input .mac.erb template") do |value|
    config[:template] = value
  end

  opts.on("--output PATH", "Output generated .mac file") do |value|
    config[:output] = value
  end

  opts.on("--output-dir PATH", "Directory for ROOT output") do |value|
    config[:output_dir] = value
  end

  opts.on("--rootfile PATH", "Explicit ROOT output file") do |value|
    config[:rootfile] = value
  end

  opts.on("--run-tag VALUE", "Filename-safe run tag") do |value|
    config[:run_tag] = value
  end

  opts.on("--run-nr VALUE", "Run number") do |value|
    config[:run_nr] = value
  end

  opts.on("--particle VALUE", "Geant4 particle, e.g. e+, e-, mu+") do |value|
    config[:particle] = value
  end

  opts.on("--particle-tag VALUE", "Filename-safe particle tag, e.g. e_pos") do |value|
    config[:particle_tag] = value
  end

  opts.on("--part VALUE", "Part index") do |value|
    config[:part] = value
  end

  opts.on("--beam-momentum VALUE", "Beam momentum in MeV") do |value|
    config[:beam_momentum] = value
  end

  opts.on("--n-events VALUE", "Number of events") do |value|
    config[:n_events] = value
  end

  opts.on("--seed-1 VALUE", "First random seed") do |value|
    config[:seed_1] = value
  end

  opts.on("--seed-2 VALUE", "Second random seed") do |value|
    config[:seed_2] = value
  end
end.parse!

missing = []
missing << "--template" unless config[:template]
missing << "--output" unless config[:output]
missing << "--run-nr" unless config[:run_nr]

unless missing.empty?
  warn "Missing required options: #{missing.join(', ')}"
  exit 2
end

template_path = File.expand_path(config[:template])
output_path = File.expand_path(config[:output])

run_nr = config[:run_nr]
particle = config[:particle]
particle_tag = config[:particle_tag]
part = config[:part]
beam_momentum = config[:beam_momentum]
n_events = config[:n_events]
seed_1 = config[:seed_1]
seed_2 = config[:seed_2]
run_tag = config[:run_tag] || "mc#{run_nr}_rad2_#{particle_tag}_part#{part}"

output_dir =
  if config[:output_dir]
    File.expand_path(config[:output_dir])
  else
    "/data4/MC/John/mc#{run_nr}/Sim"
  end

rootfile =
  if config[:rootfile]
    File.expand_path(config[:rootfile])
  else
    File.join(
      output_dir,
      "#{run_tag}_g4psi.root"
    )
  end

FileUtils.mkdir_p(File.dirname(output_path))
FileUtils.mkdir_p(File.dirname(rootfile))

template = File.read(template_path)
rendered = ERB.new(template, trim_mode: "-").result(binding)

File.write(output_path, rendered)

puts rootfile