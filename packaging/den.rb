# PREPARED, NOT PUBLISHED. Shape: lope bc388673 packaging/lope.rb.
# Source build from a future tag; no dependency on a moving wolf formula.
class Den < Formula
  desc "Git-compatible VCS in wolf (M0 refusal scaffold)"
  homepage "https://github.com/wolffe-lang/den"
  url "https://github.com/wolffe-lang/den/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "RELEASE-LANE-FILLS-THIS"
  license "GPL-3.0-only"
  depends_on "llvm" => :build

  resource "wolf" do
    on_macos do
      on_arm do
        url "https://github.com/wolffe-lang/wolf-lang/releases/download/v0.2.36/wolf-0.2.36-aarch64-apple-darwin.tar.gz"
        sha256 "b79d55845f349d56789d9d1cb057ee88b5a7128d3b6dd77ca070707cfa4aa632"
      end
    end
    on_linux do
      on_intel do
        url "https://github.com/wolffe-lang/wolf-lang/releases/download/v0.2.36/wolf-0.2.36-x86_64-unknown-linux-gnu.tar.gz"
        sha256 "d383c74c8cd123b9d9dfaa268271d4f004294f85c2b230237d0ef07027d9500d"
      end
    end
  end

  def install
    source = buildpath
    resource("wolf").stage do
      odie "bundled std pin drift" unless (Pathname.pwd/"std/STD-REV").read.strip == "78b9d3cbc41d51db44d18c40b6694403644d1c83"
      ENV["WOLF_STD"] = (Pathname.pwd/"std").to_s
      system "./wolf", "build", "--release", "--deny-warnings", source/"src/den.lu", "-o", source/"den"
    end
    bin.install "den"
    doc.install "README.md", "CHANGELOG.md"
  end

  test do
    assert_equal "den 0.0.0 (built with wolf 0.2.36)\n", shell_output("#{bin}/den --version")
    assert_match "not yet implemented: commit", shell_output("#{bin}/den commit 2>&1", 2)
  end
end
