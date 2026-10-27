library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

entity digital_mixer is
  generic (
    DATA_WIDTH : positive := 16;
    PHASE_WIDTH : positive := 32;
    LUT_DEPTH : positive := 10;
    DITHER_WIDTH : positive := 24
  );
  port (
    clk : in std_logic;
    rst : in std_logic;
    ce : in std_logic;
    xin_re : in signed(DATA_WIDTH-1 downto 0);
    xin_im : in signed(DATA_WIDTH-1 downto 0);
    freq_word : in unsigned(PHASE_WIDTH-1 downto 0);
    xout_re : out signed(2*DATA_WIDTH downto 0);
    xout_im : out signed(2*DATA_WIDTH downto 0)
  );
end entity digital_mixer;

architecture rtl of digital_mixer is

  -- Full-wave sine LUT (sin and cos via quarter-wave address offset)
  type lut_t is array (0 to 2**LUT_DEPTH-1) of signed(DATA_WIDTH-1 downto 0);
  function init_sine return lut_t is
    variable l : lut_t;
    variable angle : real;
  begin
    for i in 0 to 2**LUT_DEPTH-1 loop
      angle := real(i) * MATH_PI * 2.0 / real(2**LUT_DEPTH);
      l(i) := to_signed(integer(sin(angle) * (2.0**(DATA_WIDTH-1)-1.0)), DATA_WIDTH);
    end loop;
    return l;
  end function;
  constant SINE_LUT : lut_t := init_sine;

  signal phase_acc : unsigned(PHASE_WIDTH-1 downto 0) := (others => '0');
  signal lfsr : unsigned(DITHER_WIDTH-1 downto 0) := (others => '0');
  signal dither : unsigned(PHASE_WIDTH-1 downto 0) := (others => '0');
  signal phase_dith : unsigned(PHASE_WIDTH-1 downto 0) := (others => '0');
  signal addr : unsigned(LUT_DEPTH-1 downto 0) := (others => '0');
  signal nco_sin : signed(DATA_WIDTH-1 downto 0) := (others => '0');
  signal nco_cos : signed(DATA_WIDTH-1 downto 0) := (others => '0');
  signal mul_re : signed(2*DATA_WIDTH downto 0) := (others => '0');
  signal mul_im : signed(2*DATA_WIDTH downto 0) := (others => '0');
begin

  --------------------------------------------------------------------------
  -- Phase accumulator
  --------------------------------------------------------------------------
  process(clk, rst)
  begin
    if rst = '1' then
      phase_acc <= (others => '0');
    elsif rising_edge(clk) then
      if ce = '1' then
        phase_acc <= phase_acc + freq_word;
      end if;
    end if;
  end process;

  --------------------------------------------------------------------------
  -- Mandatory phase dither: 24-bit LFSR
  -- Polynomial: x^24 + x^23 + x^22 + x^17 + 1  (maximal length)
  -- Dither is injected into the phase bits that are truncated when forming
  -- the LUT address, so truncation error is no longer periodic; spurs
  -- collapse into a noise floor.
  --------------------------------------------------------------------------
  process(clk, rst)
    variable fb : std_logic;
  begin
    if rst = '1' then
      lfsr <= (others => '1');  -- non-zero seed required
    elsif rising_edge(clk) then
      if ce = '1' then
        fb := lfsr(23) xor lfsr(22) xor lfsr(21) xor lfsr(16);
        lfsr <= lfsr(DITHER_WIDTH-2 downto 0) & fb;
      end if;
    end if;
  end process;

  -- Align LFSR into PHASE_WIDTH (zero-extend or truncate as needed)
  dither <= resize(lfsr, PHASE_WIDTH);

  phase_dith <= phase_acc + dither;

  -- LUT address = top LUT_DEPTH bits of *dithered* phase
  addr    <= phase_dith(PHASE_WIDTH-1 downto PHASE_WIDTH-LUT_DEPTH);
  nco_sin <= SINE_LUT(to_integer(addr));
  -- Cosine = sine(+90 deg) = address + 1/4 LUT length
  nco_cos <= SINE_LUT(to_integer(addr + 2**(LUT_DEPTH-2)));

  --------------------------------------------------------------------------
  -- Complex multiply: (xin_re + j xin_im) * (cos + j sin)
  --------------------------------------------------------------------------
  process(clk, rst)
  begin
    if rst = '1' then
      mul_re <= (others => '0');
      mul_im <= (others => '0');
    elsif rising_edge(clk) then
      if ce = '1' then
        mul_re <= resize(xin_re * nco_cos + xin_im * nco_sin, 2*DATA_WIDTH+1);
        mul_im <= resize(xin_im * nco_cos - xin_re * nco_sin, 2*DATA_WIDTH+1);
      end if;
    end if;
  end process;

  xout_re <= mul_re;
  xout_im <= mul_im;

end architecture rtl;