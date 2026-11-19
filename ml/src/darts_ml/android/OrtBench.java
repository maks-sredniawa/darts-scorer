import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtSession;
import java.nio.FloatBuffer;
import java.util.Collections;
import java.util.Random;

public final class OrtBench {
    public static void main(String[] args) throws Exception {
        String model = args[0];
        int threads = Integer.parseInt(args[1]);
        int size = Integer.parseInt(args[2]);
        int warmup = Integer.parseInt(args[3]);
        int runs = Integer.parseInt(args[4]);

        OrtEnvironment env = OrtEnvironment.getEnvironment();
        OrtSession.SessionOptions options = new OrtSession.SessionOptions();
        if (threads > 0) {
            options.setIntraOpNumThreads(threads);
        }
        long start = System.nanoTime();
        OrtSession session = env.createSession(model, options);
        System.out.println("init_us=" + (System.nanoTime() - start) / 1000);

        float[] pixels = new float[3 * size * size];
        Random random = new Random(0);
        for (int i = 0; i < pixels.length; i++) {
            pixels[i] = random.nextFloat();
        }
        String input = session.getInputNames().iterator().next();
        try (OnnxTensor tensor = OnnxTensor.createTensor(env, FloatBuffer.wrap(pixels), new long[] {1, 3, size, size})) {
            for (int i = 0; i < warmup + runs; i++) {
                long t = System.nanoTime();
                session.run(Collections.singletonMap(input, tensor)).close();
                System.out.println((i < warmup ? "warmup_us=" : "run_us=") + (System.nanoTime() - t) / 1000);
            }
        }
        session.close();
    }
}
