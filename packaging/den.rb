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
        url "https://github.com/wolffe-lang/wolf-lang/releases/download/v0.2.35/wolf-0.2.35-aarch64-apple-darwin.tar.gz"
        sha256 "240b84d079b1b9a0d88681ac08fca4816f84778e2d6c94c435ceb2dd6a5f042a"
      end
    end
    on_linux do
      on_intel do
        url "https://github.com/wolffe-lang/wolf-lang/releases/download/v0.2.35/wolf-0.2.35-x86_64-unknown-linux-gnu.tar.gz"
        sha256 "4cc4045bbbb605c07835bc4f32685953c784eeef4cd3139a48b457dfc90dad1a"
      end
    end
  end

  def install
    source = buildpath
    resource("wolf").stage do
      odie "bundled std pin drift" unless (Pathname.pwd/"std/STD-REV").read.strip == "2386522eb059cca5a84108562c2c0a0e72345d34"
      ENV["WOLF_STD"] = (Pathname.pwd/"std").to_s
      system "./wolf", "build", "--release", "--deny-warnings", source/"src/den.lu", "-o", source/"den"
    end
    bin.install "den"
    doc.install "README.md", "CHANGELOG.md"
  end

  test do
    assert_equal "den 0.0.0 (built with wolf 0.2.35)\n", shell_output("#{bin}/den --version")
    assert_match "not yet implemented: commit", shell_output("#{bin}/den commit 2>&1", 2)
  end
end
