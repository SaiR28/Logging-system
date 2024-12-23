import serial
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy.interpolate import griddata

class RobustThermalHeatmap:
    def __init__(self, port='COM5', baudrate=115200):
        """
        Initialize robust thermal heatmap visualization
        """
        # Serial connection setup
        try:
            self.ser = serial.Serial(port, baudrate, timeout=2)
            self.ser.reset_input_buffer()
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            raise

        # Matplotlib setup with explicit backend
        plt.switch_backend('TkAgg')
        
        # Create figure with multiple subplots
        self.fig, (self.ax1, self.ax2) = plt.subplots(1, 2, figsize=(15, 6))
        self.fig.suptitle('Thermal Mapping', fontsize=16)
        
        # Initial data (all zeros)
        initial_data = np.zeros((8, 8))
        
        # Original 8x8 heatmap
        self.heatmap_original = self.ax1.imshow(
            initial_data, 
            cmap='inferno', 
            interpolation='nearest',
            vmin=15, 
            vmax=25
        )
        self.ax1.set_title('Original 8x8 Grid')
        self.fig.colorbar(self.heatmap_original, ax=self.ax1, label='Temperature (°C)')
        
        # Interpolated high-resolution heatmap
        self.heatmap_interpolated = self.ax2.imshow(
            np.zeros((80, 80)), 
            cmap='inferno', 
            interpolation='bicubic',
            vmin=5, 
            vmax=25
        )
        self.ax2.set_title('Interpolated View')
        self.fig.colorbar(self.heatmap_interpolated, ax=self.ax2, label='Temperature (°C)')
        
        # Prepare for animation
        plt.tight_layout()
    
    def interpolate_thermal_data(self, thermal_data):
        """
        Interpolate thermal data to higher resolution
        """
        # Original grid coordinates
        x = np.linspace(0, 7, 8)
        y = np.linspace(0, 7, 8)
        X, Y = np.meshgrid(x, y)
        
        # High-resolution grid
        xi = np.linspace(0, 7, 80)
        yi = np.linspace(0, 7, 80)
        Xi, Yi = np.meshgrid(xi, yi)
        
        # Interpolate using griddata
        try:
            interpolated_data = griddata(
                (X.ravel(), Y.ravel()), 
                thermal_data.ravel(), 
                (Xi, Yi), 
                method='cubic'
            )
            return interpolated_data
        except Exception as e:
            print(f"Interpolation error: {e}")
            return np.zeros((80, 80))
    
    def read_thermal_data(self):
        """
        Read thermal data frame from serial
        """
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                # Clear any buffered input
                self.ser.reset_input_buffer()
                
                # Wait for 'Thermal data:' marker
                while True:
                    line = self.ser.readline().decode('utf-8').strip()
                    if 'Thermal data:' in line:
                        break
                
                # Read the next 8 lines (8x8 grid)
                data_lines = []
                for _ in range(8):
                    line = self.ser.readline().decode('utf-8').strip()
                    data_lines.append(line.split())
                
                # Flatten and convert to numpy array
                pixels = [float(val) for line in data_lines for val in line]
                if len(pixels) == 64:
                    return np.array(pixels).reshape(8, 8)
                
            except (ValueError, serial.SerialException) as e:
                print(f"Data reading error (attempt {attempt+1}): {e}")
                continue
        
        # If all attempts fail, return a default array
        print("Failed to read thermal data after multiple attempts")
        return np.zeros((8, 8))
    
    def update(self, frame):
        """
        Update heatmaps with new thermal data
        """
        try:
            # Read new frame
            current_frame = self.read_thermal_data()
            
            # Update original heatmap
            self.heatmap_original.set_array(current_frame)
            
            # Interpolate and update high-res heatmap
            interpolated_frame = self.interpolate_thermal_data(current_frame)
            self.heatmap_interpolated.set_array(interpolated_frame)
            
            return [self.heatmap_original, self.heatmap_interpolated]
        
        except Exception as e:
            print(f"Update error: {e}")
            return []
    
    def start_visualization(self, num_frames=500):
        """
        Start the visualization
        """
        try:
            # Create animation
            self.anim = FuncAnimation(
                self.fig, 
                self.update, 
                frames=num_frames, 
                interval=1000,  # 1 second between frames
                blit=True
            )
            
            # Show plot
            plt.show()
        
        except Exception as e:
            print(f"Visualization error: {e}")

def main():
    try:
        # Create robust thermal heatmap instance
        thermal_map = RobustThermalHeatmap()
        
        # Start visualization
        thermal_map.start_visualization()
    
    except Exception as e:
        print(f"Main error: {e}")

if __name__ == '__main__':
    main()

# Dependencies:
# pip install pyserial numpy matplotlib scipy