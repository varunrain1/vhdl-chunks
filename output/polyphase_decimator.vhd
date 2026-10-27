library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

entity polyphase_decimator is
  generic (
    DATA_WIDTH : positive := 16;
    FACTOR : positive := 4;
    TAPS_PER_PHASE : positive := 8;
    COEFF_WIDTH : positive := 16
  );
  port (
    clk : in std_logic;
    rst : in std_logic;
    ce_in : in std_logic;
    din : in signed(DATA_WIDTH-1 downto 0);
    ce_out : out std_logic;
    dout : out signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0)
  );
end entity polyphase_decimator;

architecture rtl of polyphase_decimator is
  type phase_coeff_t is array (0 to TAPS_PER_PHASE-1) of signed(COEFF_WIDTH-1 downto 0);
  type all_coeff_t is array (0 to FACTOR-1) of phase_coeff_t;
  constant PHASE_COEFFS : all_coeff_t := (
    (to_signed(-8, 16), to_signed(82, 16), to_signed(-391, 16), to_signed(1070, 16), to_signed(3212, 16), to_signed(294, 16), to_signed(-233, 16), to_signed(68, 16)),
    (to_signed(10, 16), to_signed(45, 16), to_signed(-425, 16), to_signed(1963, 16), to_signed(2750, 16), to_signed(-217, 16), to_signed(-64, 16), to_signed(37, 16)),
    (to_signed(37, 16), to_signed(-64, 16), to_signed(-217, 16), to_signed(2750, 16), to_signed(1963, 16), to_signed(-425, 16), to_signed(45, 16), to_signed(10, 16)),
    (to_signed(68, 16), to_signed(-233, 16), to_signed(294, 16), to_signed(3212, 16), to_signed(1070, 16), to_signed(-391, 16), to_signed(82, 16), to_signed(-8, 16))
  );

  type phase_delay_t is array (0 to TAPS_PER_PHASE-1) of signed(DATA_WIDTH-1 downto 0);
  type all_phases_t  is array (0 to FACTOR-1) of phase_delay_t;

  signal phase_cnt : integer range 0 to FACTOR-1 := 0;
  signal delays : all_phases_t := (others => (others => (others => '0')));
  signal phase_mac : signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0) := (others => '0');
  signal acc : signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0) := (others => '0');
  signal out_valid : std_logic := '0';
begin

  process(clk, rst)
    variable sum   : signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0);
    variable phase : integer;
  begin
    if rst = '1' then
      phase_cnt <= 0;
      delays    <= (others => (others => (others => '0')));
      phase_mac <= (others => '0');
      acc       <= (others => '0');
      out_valid <= '0';
    elsif rising_edge(clk) then
      out_valid <= '0';
      if ce_in = '1' then
        phase := phase_cnt;

        -- shift the selected phase delay line
        delays(phase)(0) <= din;
        for t in 1 to TAPS_PER_PHASE-1 loop
          delays(phase)(t) <= delays(phase)(t-1);
        end loop;

        -- MAC for the current phase
        sum := (others => '0');
        for t in 0 to TAPS_PER_PHASE-1 loop
          sum := sum + resize(delays(phase)(t) * PHASE_COEFFS(phase)(t), sum'length);
        end loop;

        if phase_cnt = 0 then
          phase_mac <= sum;                 -- start new accumulation
        else
          phase_mac <= phase_mac + sum;     -- accumulate all phases
        end if;

        if phase_cnt = FACTOR-1 then
          phase_cnt <= 0;
          acc       <= phase_mac + sum;     -- final sum of every phase
          out_valid <= '1';
        else
          phase_cnt <= phase_cnt + 1;
        end if;
      end if;
    end if;
  end process;
  ce_out <= out_valid;
  dout   <= acc;

end architecture rtl;