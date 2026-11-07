
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

entity gnss_mixer is
    port (
        clk     : in  std_logic;
        rst     : in  std_logic;

        i_in    : in  integer;
        q_in    : in  integer;

        i_out   : out integer;
        q_out   : out integer
    );
end entity;

architecture sim of gnss_mixer is

    constant FS       : real := 122.88e6;
    constant FC       : real := 8.7e6;
    constant PHASE_W  : integer := 13;
    constant DDS_MAX  : integer := 32767;

    constant FTW : unsigned(PHASE_W-1 downto 0) :=
        to_unsigned(580,13);

    signal phase_acc : unsigned(PHASE_W-1 downto 0) :=
                       (others => '0');

begin

    process(clk)
        variable phase_index : integer;
        variable angle       : real;

        variable dds_i       : integer;
        variable dds_q       : integer;

        variable mix_i       : integer;
        variable mix_q       : integer;

    begin
        if rising_edge(clk) then

            if rst = '1' then

                phase_acc <= (others => '0');
                i_out <= 0;
                q_out <= 0;

            else

                -- DDS phase from upper 16 bits
                phase_index :=  to_integer(phase_acc);

                angle := 2.0 * MATH_PI * real(phase_index) / 8192.0;

                -- Generate complex correction carrier
                dds_i := integer(
                    real(DDS_MAX) * cos(angle)
                );

                dds_q := integer(
                    -real(DDS_MAX) * sin(angle)
                );

                -- Complex multiplication
                mix_i := (
                    i_in * dds_i -
                    q_in * dds_q
                ) / DDS_MAX;

                mix_q := (
                    i_in * dds_q +
                    q_in * dds_i
                ) / DDS_MAX;

                i_out <= mix_i;
                q_out <= mix_q;

                -- Advance DDS phase
                phase_acc <= phase_acc + FTW;

            end if;
        end if;
    end process;

end architecture;
